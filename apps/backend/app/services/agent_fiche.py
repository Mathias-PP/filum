"""Orchestrateur de fiche : déroule les étages ICM du workspace.

Une fiche complète ne tient pas dans un seul tour de modèle. L'orchestrateur
découpe le travail en étages (brief, sources, annotations, extraits,
connexions, relecture, publication) et lance **une boucle d'agent par étage**,
avec pour instruction le ``CONTEXT.md`` de cet étage, tel qu'il vit dans le
workspace du créateur.

Deux conséquences voulues :

- l'étage est la seule unité que le modèle voit à la fois, donc son contexte
  reste borné et son budget de tours aussi ;
- éditer un ``CONTEXT.md`` dans le workspace change le comportement de
  l'orchestrateur, sans toucher au code.

**Les checkpoints humains ne sont pas une mécanique à part** : les actions
sensibles (``publish_card``, attestation, suppression) passent déjà par
``approuver`` dans la boucle. L'étage de publication s'arrête donc de lui-même
sur une demande d'approbation, et une fiche ne part jamais en ligne sans un
accord explicite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.tool import AgentTool
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.services import agent_workspace
from app.services.agent import Approuver, Emitter, boucle


@dataclass(frozen=True)
class Etape:
    """Un étage ICM : d'où viennent ses règles, où atterrit son compte rendu."""

    id: str
    sortie: str

    @property
    def instructions(self) -> str:
        return f"stages/{self.id}/CONTEXT.md"


#: Les sept étages, dans l'ordre où ils doivent se dérouler. L'ordre est ici
#: plutôt que dans un fichier du workspace parce qu'un étage qui saute son
#: rang produit une fiche incohérente (des extraits avant les sources).
ETAPES: tuple[Etape, ...] = (
    Etape("01-brief", "runs/{slug}/00-brief.md"),
    Etape("02-sources-collectees", "runs/{slug}/01-sources.md"),
    Etape("03-annotations", "runs/{slug}/02-annotations.md"),
    Etape("04-extraits", "runs/{slug}/03-extraits.md"),
    Etape("05-connexions", "runs/{slug}/04-connexions.md"),
    Etape("06-relecture", "runs/{slug}/05-relecture.md"),
    Etape("07-publication", "runs/{slug}/06-publication.md"),
)

#: Ce que l'orchestrateur rappelle au modèle à chaque étage, en plus du
#: ``CONTEXT.md``. La boucle a déjà son prompt système ; ceci cadre la mission.
_CADRE = (
    "Tu déroules un étage de la création d'une fiche Philum. Les règles de "
    "l'étage sont ci-dessous, elles font autorité. Utilise les outils pour "
    "agir réellement : lire une page, poser une source, vérifier un extrait. "
    "N'invente jamais un verbatim. Termine par un compte rendu court de ce "
    "que tu as fait à cet étage, qui servira de contexte à l'étage suivant."
)


class FicheError(ValueError):
    """Le run ne peut pas démarrer ou continuer."""


def _prefixe(slug: str) -> str:
    return f"runs/{slug}"


async def etat(db: AsyncSession, creator_id: UUID, slug: str) -> dict[str, Any]:
    """Où en est un run : quels étages ont déjà déposé leur compte rendu."""
    fichiers = await agent_workspace.lister(db, creator_id, prefix=_prefixe(slug))
    presents = {str(e["path"]) for e in fichiers if e.get("type") == "file"}
    etapes = [
        {"id": etape.id, "output": etape.sortie.format(slug=slug), "fait": False}
        for etape in ETAPES
    ]
    for entree in etapes:
        entree["fait"] = str(entree["output"]) in presents
    return {
        "slug": slug,
        "demarre": bool(presents),
        "etapes": etapes,
        "fichiers": sorted(presents),
    }


async def _instructions(db: AsyncSession, creator_id: UUID, etape: Etape) -> str:
    fichier = await agent_workspace.lire(db, creator_id, etape.instructions)
    if fichier is None:
        raise FicheError(
            f"L'étage {etape.id} n'a pas de règles dans ton workspace "
            f"({etape.instructions} est absent)."
        )
    return fichier.content


def _amorce(etape: Etape, regles: str, contexte: str, content_url: str, slug: str) -> str:
    entete = (
        f"{_CADRE}\n\n"
        f"Étage : {etape.id}\n"
        f"Slug de la fiche : {slug}\n"
        f"Contenu à documenter : {content_url}\n"
    )
    if contexte:
        entete += f"\nCe que les étages précédents ont produit :\n{contexte}\n"
    return f"{entete}\n--- Règles de l'étage ---\n{regles}"


async def lancer(
    db: AsyncSession,
    user: User,
    provider: AgentProvider,
    *,
    slug: str,
    content_url: str,
    emit: Emitter,
    approuver: Approuver,
    transport: httpx.AsyncBaseTransport | None = None,
    registre: dict[str, AgentTool] | None = None,
    depuis: str | None = None,
) -> None:
    """Déroule les étages et écrit chaque compte rendu dans le workspace.

    ``depuis`` reprend un run interrompu à l'étage nommé : les comptes rendus
    déjà écrits sont relus comme contexte au lieu d'être refaits, pour qu'une
    coupure de réseau ne coûte pas la fiche entière.

    Une erreur émise par la boucle arrête le run : continuer sur un étage
    raté produirait des extraits accrochés à des sources qui n'existent pas.
    """
    restantes = list(ETAPES)
    if depuis is not None:
        index = next((i for i, e in enumerate(ETAPES) if e.id == depuis), None)
        if index is None:
            raise FicheError(f"Étage inconnu : {depuis}.")
        restantes = list(ETAPES[index:])

    contexte: list[str] = []
    for etape in ETAPES:
        if etape in restantes:
            break
        fichier = await agent_workspace.lire(db, user.id, etape.sortie.format(slug=slug))
        if fichier is not None:
            contexte.append(f"## {etape.id}\n{fichier.content}")

    for etape in restantes:
        regles = await _instructions(db, user.id, etape)
        await emit({"type": "stage_start", "payload": {"stage": etape.id}})

        echecs: list[str] = []
        compte_rendu: list[str] = []

        async def capter(
            event: dict[str, Any],
            _etape: Etape = etape,
            _echecs: list[str] = echecs,
            _rendu: list[str] = compte_rendu,
        ) -> None:
            type_ = event.get("type")
            if type_ == "message_delta":
                _rendu.append(event["payload"]["delta"])
            elif type_ == "error":
                _echecs.append(str(event["payload"].get("message", "")))
            elif type_ == "done":
                # La boucle dit « done » à la fin de chaque étage. Le client,
                # lui, n'a droit qu'à un seul `done` : celui de la fiche.
                return
            await emit({**event, "stage": _etape.id})

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": _amorce(etape, regles, "\n\n".join(contexte), content_url, slug),
            }
        ]
        await boucle(
            db,
            user,
            provider,
            messages,
            capter,
            approuver,
            transport=transport,
            registre=registre,
        )
        if echecs:
            await emit({"type": "stage_failed", "payload": {"stage": etape.id}})
            return

        texte = "".join(compte_rendu).strip()
        sortie = etape.sortie.format(slug=slug)
        await agent_workspace.ecrire(db, user.id, sortie, texte or "(aucun compte rendu)")
        await db.commit()
        contexte.append(f"## {etape.id}\n{texte}")
        await emit({"type": "stage_done", "payload": {"stage": etape.id, "output": sortie}})

    await emit({"type": "done", "payload": {"reason": "fiche_complete", "slug": slug}})
