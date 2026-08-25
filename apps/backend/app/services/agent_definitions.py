"""Agents nommés : chargement et validation des fichiers `agents/*.yaml`.

Un agent n'est pas une ligne de base : c'est un fichier du workspace du
créateur, au même titre que ses règles de rédaction. Une seule maison par
fait (invariant ICM) : le fichier est la définition, et il s'édite avec
l'éditeur de workspace déjà en place.

Une définition invalide n'est jamais chargée à moitié. Le fichier est écarté
avec sa raison, le sélecteur d'agent ne le montre pas, et le créateur voit
l'erreur dans la liste au lieu de la découvrir au milieu d'une conversation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.registry import noms_outils_connus
from app.models.workspace_file import WorkspaceFile
from app.services.agent_workspace import SEED_DIR, WorkspaceError, normaliser_chemin

#: Racine des définitions d'agents dans le workspace.
DOSSIER = "agents/"

#: Slug de l'agent utilisé quand la session n'en désigne aucun. Son fichier
#: peut avoir été supprimé par le créateur : dans ce cas la boucle retombe sur
#: le comportement historique (tous les outils, tout `shared/`).
SLUG_DEFAUT = "assistant"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LAYERS = ("L0", "L1", "L2", "L3", "L4")


class DefinitionInvalideError(ValueError):
    """Le fichier existe mais ne décrit pas un agent exploitable."""


@dataclass(frozen=True)
class AgentDefinition:
    """Un agent chargé et validé."""

    slug: str
    name: str
    contract: str
    system_prompt: str
    tools: tuple[str, ...]
    context: tuple[str, ...] = ()
    layer: str | None = None
    model_hint: str | None = None
    #: Nombre maximal de tours autorisés pour cet agent. Par défaut, 24 tours.
    quota_tours: int = 24
    #: Vrai si le slug fait partie des agents livrés avec Philum. Sert à
    #: distinguer « recréé par Restaurer template » de « le vôtre ».
    builtin: bool = False
    #: Outils demandés que le serveur n'expose pas dans sa configuration
    #: courante (``web_search`` sans clé de recherche). Affichés au créateur
    #: pour qu'il comprenne pourquoi l'agent ne cherche pas.
    tools_absents: tuple[str, ...] = ()


def chemin_de(slug: str) -> str:
    return f"{DOSSIER}{slug}.yaml"


def _texte(valeur: Any, champ: str, *, obligatoire: bool = True) -> str:
    if valeur is None and not obligatoire:
        return ""
    if not isinstance(valeur, str) or not valeur.strip():
        raise DefinitionInvalideError(f"Champ « {champ} » manquant ou vide.")
    return valeur.strip()


def parser(path: str, contenu: str, *, noms_connus: frozenset[str]) -> AgentDefinition:
    """Rend la définition portée par un fichier, ou lève `DefinitionInvalideError`."""
    try:
        brut = yaml.safe_load(contenu)
    except yaml.YAMLError as exc:
        raise DefinitionInvalideError(f"YAML illisible : {exc}") from exc
    if not isinstance(brut, dict):
        raise DefinitionInvalideError("Le fichier doit contenir un dictionnaire YAML.")

    slug = _texte(brut.get("slug"), "slug")
    if not _SLUG_RE.match(slug):
        raise DefinitionInvalideError(f"Slug « {slug} » invalide : attendu en kebab-case.")
    attendu = chemin_de(slug)
    if path != attendu:
        raise DefinitionInvalideError(f"Le slug « {slug} » impose le chemin « {attendu} ».")

    tools_bruts = brut.get("tools")
    if not isinstance(tools_bruts, list) or not tools_bruts:
        raise DefinitionInvalideError(
            "Champ « tools » manquant : un agent sans outil ne sert à rien."
        )
    tools: list[str] = []
    for nom in tools_bruts:
        if not isinstance(nom, str) or nom not in noms_connus:
            raise DefinitionInvalideError(f"Outil inconnu : {nom!r}.")
        if nom not in tools:
            tools.append(nom)

    context: list[str] = []
    for chemin in brut.get("context") or []:
        if not isinstance(chemin, str):
            raise DefinitionInvalideError(f"Chemin de contexte invalide : {chemin!r}.")
        try:
            normalise = normaliser_chemin(chemin)
        except WorkspaceError as exc:
            raise DefinitionInvalideError(f"Chemin de contexte refusé ({chemin}) : {exc}") from exc
        if normalise not in context:
            context.append(normalise)

    layer = brut.get("layer")
    if layer is not None and layer not in _LAYERS:
        raise DefinitionInvalideError(f"Layer « {layer} » inconnu : attendu {', '.join(_LAYERS)}.")

    return AgentDefinition(
        slug=slug,
        name=_texte(brut.get("name"), "name"),
        contract=_texte(brut.get("contract"), "contract"),
        system_prompt=_texte(brut.get("system_prompt"), "system_prompt"),
        tools=tuple(tools),
        context=tuple(context),
        layer=layer,
        model_hint=_texte(brut.get("model_hint"), "model_hint", obligatoire=False) or None,
    )


@dataclass(frozen=True)
class DefinitionRejetee:
    path: str
    raison: str


async def _fichiers_agents(db: AsyncSession, creator_id: UUID) -> list[WorkspaceFile]:
    result = await db.execute(
        select(WorkspaceFile)
        .where(
            WorkspaceFile.creator_id == creator_id,
            WorkspaceFile.path.startswith(DOSSIER),
        )
        .order_by(WorkspaceFile.path)
    )
    return [f for f in result.scalars().all() if f.path.endswith((".yaml", ".yml"))]


def _slugs_livres() -> frozenset[str]:
    """Slugs des agents fournis avec Philum, lus dans le snapshot du seed."""
    dossier = SEED_DIR / "agents"
    if not dossier.is_dir():
        return frozenset()
    return frozenset(f.stem for f in dossier.glob("*.yaml"))


async def lister(
    db: AsyncSession, creator_id: UUID
) -> tuple[list[AgentDefinition], list[DefinitionRejetee]]:
    """Rend (agents valides, fichiers rejetés avec leur raison)."""
    exposes = frozenset(noms_outils_connus(exposes_seulement=True))
    connus = noms_outils_connus()
    livres = _slugs_livres()

    valides: list[AgentDefinition] = []
    rejetes: list[DefinitionRejetee] = []
    for fichier in await _fichiers_agents(db, creator_id):
        try:
            definition = parser(fichier.path, fichier.content, noms_connus=connus)
        except DefinitionInvalideError as exc:
            rejetes.append(DefinitionRejetee(path=fichier.path, raison=str(exc)))
            continue
        valides.append(
            replace(
                definition,
                builtin=definition.slug in livres,
                tools_absents=tuple(nom for nom in definition.tools if nom not in exposes),
            )
        )
    valides.sort(key=lambda d: (not d.builtin, d.slug != SLUG_DEFAUT, d.name))
    return valides, rejetes


async def obtenir(db: AsyncSession, creator_id: UUID, slug: str) -> AgentDefinition | None:
    """Rend l'agent de ce slug, ou None s'il est absent ou invalide."""
    if not slug:
        return None
    valides, _ = await lister(db, creator_id)
    return next((d for d in valides if d.slug == slug), None)
