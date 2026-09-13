"""Deroule guide d'une fiche sujet, pilote par le serveur.

Mesure du 2026-09-13 (conversations « arthrose ») : laisse libre, l'agent
repondait de memoire, posait des sources sans extrait, reformulait les
verbatims et ne cherchait jamais ce qui nuance. Les outils de deroule
(`fiche_etapes`, `fiche_state`) n'ont pas ete appeles une seule fois : un petit
modele ne decouvre pas seul un deroule decrit dans un fichier.

Ici le serveur tient l'ordre. Une question devient une fiche sujet en cinq
etapes, et chaque etape est une boucle d'agent qui ne voit que ses outils :

1. recherche : la fiche existante ou creee, et des sources dont une qui nuance ;
2. sources : `add_source` sans position ;
3. extraits : `find_passage` puis `add_excerpt` ;
4. positions : `update_source`, qui exige deja un extrait ;
5. bilan : la reponse au createur, tiree des seuls extraits poses.

Le compte rendu de chaque etape sert de contexte a la suivante. Le deroule
tourne dans le tour detache du chat : reprise apres une coupure, fiche en
direct et bouton « Arrêter » restent ceux de la conversation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.registry import construire_registre, filtrer
from app.agent_tools.tool import AgentTool
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.services.agent import Approuver, Emitter, boucle
from app.services.agent_definitions import AgentDefinition

#: Une demande explicite de fiche, avec ou sans l'orthographe exacte.
_DEMANDE_DE_FICHE = re.compile(
    r"\b(?:fais|fait|faire|cr[ée]{1,2}[erz]{0,2}|pr[ée]pare|r[ée]dige|monte|construi\w*)\b"
    r"[^.?!\n]{0,40}\bfiche\b",
    re.IGNORECASE,
)

#: Une question de fond, en tete d'une conversation neuve.
_QUESTION = re.compile(
    r"^\s*(?:comment|pourquoi|quels?|quelles?|qu['’]est-ce|est-ce que|faut-il|"
    r"peut-on|combien|existe-t-il|y a-t-il)\b.*\?\s*$",
    re.IGNORECASE | re.DOTALL,
)

#: Une question qui porte sur Philum lui-meme, pas sur un sujet a documenter.
_USAGE_PHILUM = re.compile(
    r"\b(?:philum|fiches?|extraits?|sources?|publier|publication|cl[ée]s?|agents?|"
    r"mode gratuit|compte|workspace)\b",
    re.IGNORECASE,
)

#: Au-dela, un premier message est une consigne detaillee, pas une question a
#: documenter : le deroule ne doit pas la reduire a cinq etapes fixes.
_QUESTION_LONGUEUR_MAX = 300


def est_demande_de_fiche(message: str, *, premier_message: bool) -> bool:
    """Le message demande-t-il une fiche sujet ?

    Une adresse dans le message designe un contenu a documenter, que le deroule
    sujet ne traite pas : la conversation reste libre.
    """
    if "http://" in message or "https://" in message:
        return False
    if _DEMANDE_DE_FICHE.search(message):
        return True
    return (
        premier_message
        and len(message) <= _QUESTION_LONGUEUR_MAX
        and bool(_QUESTION.match(message))
        and not _USAGE_PHILUM.search(message)
    )


@dataclass(frozen=True)
class Etape:
    id: str
    titre: str
    outils: tuple[str, ...]
    consigne: str


_CONSIGNE_COMMUNE = (
    "Tu déroules une étape de la création d'une fiche sujet Philum. Fais seulement "
    "ce que l'étape demande, avec les outils qu'elle te donne, puis termine par le "
    "compte rendu qu'elle demande. N'invente ni adresse, ni fait, ni verbatim."
)

ETAPES: tuple[Etape, ...] = (
    Etape(
        id="recherche",
        titre="Recherche",
        outils=("list_my_cards", "get_my_card", "create_card", "web_search", "search_cards"),
        consigne=(
            "1. Appelle list_my_cards. Si une fiche porte déjà ce sujet, appelle "
            "get_my_card avec son slug et ne crée rien.\n"
            "2. Sinon, crée une fiche sujet avec create_card(card_kind='sujet'). Le "
            "titre reprend la question.\n"
            "3. Fais plusieurs recherches avec web_search : au moins une pour les "
            "sources de référence, et au moins une pour ce qui nuance, contredit ou "
            "limite la réponse. Sans outil web_search, dis-le et arrête-toi.\n"
            "4. Termine par les sources retenues, une par ligne : l'adresse, puis ce "
            "qu'elle apporte en quelques mots. Écris « nuance » devant celles qui "
            "nuancent. Aucune adresse qu'une recherche n'a pas rendue."
        ),
    ),
    Etape(
        id="sources",
        titre="Sources",
        outils=("add_source", "list_sources", "get_url_metadata"),
        consigne=(
            "1. Pour chaque adresse retenue à l'étape de recherche, appelle "
            "add_source(card_slug, url, metadata_from='page'), sans position.\n"
            "2. Une adresse refusée : passe à la suivante.\n"
            "3. Termine par les sources ajoutées, une par ligne, avec leur identifiant."
        ),
    ),
    Etape(
        id="extraits",
        titre="Extraits",
        outils=("list_sources", "find_passage", "add_excerpt", "fetch_url"),
        consigne=(
            "1. Appelle list_sources pour avoir les identifiants.\n"
            "2. Pour chaque source, appelle find_passage avec ce qu'elle doit établir "
            "pour répondre à la question, puis add_excerpt avec un des passages rendus, "
            "recopié tel quel.\n"
            "3. Pose les passages qui portent la réponse, et ceux qui la nuancent. Si "
            "find_passage ne rend rien, passe à la source suivante.\n"
            "4. Termine par les extraits posés, source par source."
        ),
    ),
    Etape(
        id="positions",
        titre="Positions",
        outils=("get_my_card", "update_source"),
        consigne=(
            "1. Lis la fiche avec get_my_card.\n"
            "2. Pour chaque source qui porte un extrait, appelle update_source avec "
            "stance='appuie' si l'extrait soutient la réponse, 'nuance-contredit' s'il "
            "la nuance ou la contredit, 'contexte' s'il la situe.\n"
            "3. Une source sans extrait ne reçoit aucune position.\n"
            "4. Termine par les positions posées."
        ),
    ),
    Etape(
        id="bilan",
        titre="Bilan",
        outils=("get_my_card",),
        consigne=(
            "Lis la fiche avec get_my_card, puis réponds au créateur en t'appuyant "
            "uniquement sur les extraits posés :\n"
            "1. la réponse à la question, source par source ;\n"
            "2. ce qui la nuance ;\n"
            "3. ce qui n'a pas été trouvé ou pas pu être cité ;\n"
            "4. les limites.\n"
            "N'ajoute rien qui ne soit dans un extrait. Pas de plan, pas d'annonce de "
            "ce que tu vas faire."
        ),
    ),
)

#: Outils dont les arguments nomment la fiche travaillee.
_OUTILS_QUI_NOMMENT_LA_FICHE = {"get_my_card": "slug", "add_source": "card_slug"}


def _consigne(etape: Etape, rang: int, question: str, slug: str | None, contexte: str) -> str:
    morceaux = [
        f"Étape {rang} sur {len(ETAPES)} : {etape.titre}.",
        f"Question du créateur : {question}",
    ]
    if slug:
        morceaux.append(f"Fiche travaillée : {slug}")
    if contexte:
        morceaux.append(f"Ce que les étapes précédentes ont produit :\n{contexte}")
    morceaux.append(etape.consigne)
    return "\n\n".join(morceaux)


def _definition(etape: Etape) -> AgentDefinition:
    return AgentDefinition(
        slug=f"deroule-{etape.id}",
        name=f"Déroulé guidé, étape {etape.titre}",
        contract="",
        system_prompt=_CONSIGNE_COMMUNE,
        tools=etape.outils,
    )


async def derouler(
    db: AsyncSession,
    user: User,
    provider: AgentProvider,
    question: str,
    emit: Emitter,
    approuver: Approuver,
    ajouts: list[dict[str, Any]],
    heures: list[datetime],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    modele: str | None = None,
    session_id: UUID | None = None,
    replis: list[AgentProvider] | None = None,
    registre: dict[str, AgentTool] | None = None,
) -> None:
    """Deroule les cinq etapes, et verse le fil du tour dans `ajouts`.

    `ajouts` et `heures` sont remplis au fil des etapes plutot que rendus : un
    tour arrete en cours d'etape doit laisser en base ce qui a deja ete ecrit.
    Les numeros de tour des evenements sont decales d'une etape a l'autre, pour
    que la reponse finale reste le texte du dernier appel au modele.
    """
    registre = registre or construire_registre()
    comptes_rendus: list[str] = []
    etat: dict[str, Any] = {"slug": None, "decalage": 0}
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}

    for rang, etape in enumerate(ETAPES, start=1):
        await emit(
            {
                "type": "etape_guidee",
                "payload": {
                    "etape": etape.id,
                    "titre": etape.titre,
                    "rang": rang,
                    "total": len(ETAPES),
                },
            }
        )
        textes: dict[int, list[str]] = {}
        echec: list[str] = []

        async def capter(
            event: dict[str, Any],
            _textes: dict[int, list[str]] = textes,
            _echec: list[str] = echec,
        ) -> None:
            genre = event.get("type")
            charge = event.get("payload") or {}
            if isinstance(charge.get("tour"), int):
                charge = {**charge, "tour": etat["decalage"] + charge["tour"]}
                event = {**event, "payload": charge}
            if genre == "message_delta":
                _textes.setdefault(charge["tour"], []).append(charge["delta"])
            elif genre == "tool_call":
                champ = _OUTILS_QUI_NOMMENT_LA_FICHE.get(str(charge.get("name")))
                valeur = (charge.get("arguments") or {}).get(champ) if champ else None
                if isinstance(valeur, str) and valeur.strip() and etat["slug"] is None:
                    etat["slug"] = valeur.strip()
            elif genre == "tool_result" and charge.get("name") == "create_card":
                slug = (charge.get("result") or {}).get("slug")
                if isinstance(slug, str) and slug:
                    etat["slug"] = slug
            elif genre in ("done", "continuation"):
                # Une seule fin pour le deroule entier : celle du bilan.
                usage = charge.get("usage")
                if isinstance(usage, dict):
                    for cle in usage_total:
                        usage_total[cle] += int(usage.get(cle) or 0)
                return
            elif genre == "error":
                _echec.append(str(charge.get("message", "")))
            await emit(event)

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": _consigne(
                    etape, rang, question, etat["slug"], "\n\n".join(comptes_rendus)
                ),
            }
        ]
        try:
            await boucle(
                db,
                user,
                provider,
                messages,
                capter,
                approuver,
                transport=transport,
                registre=filtrer(registre, etape.outils),
                modele=modele,
                agent_def=_definition(etape),
                session_id=session_id,
                replis=replis,
            )
        finally:
            # Le prompt systeme et la consigne d'etape ne sont pas la
            # conversation : seul ce que le modele a fait l'est.
            nouveaux = [m for m in messages[2:] if m.get("role") != "system"]
            ajouts.extend(nouveaux)
            heures.extend([datetime.now(UTC).replace(tzinfo=None)] * len(nouveaux))

        if echec:
            return
        if textes:
            etat["decalage"] = max(textes)
        compte_rendu = "".join(textes[max(textes)]).strip() if textes else ""
        if rang < len(ETAPES) and compte_rendu:
            ajouts.append({"role": "assistant", "content": compte_rendu})
            heures.append(datetime.now(UTC).replace(tzinfo=None))
            comptes_rendus.append(f"## {etape.titre}\n{compte_rendu}")
        if etape.id == "recherche" and not etat["slug"]:
            await emit(
                {
                    "type": "error",
                    "payload": {
                        "message": (
                            "Aucune fiche n'a été créée ni retenue à l'étape de recherche : "
                            "le déroulé guidé s'arrête là. Reformulez la question, ou "
                            "demandez la fiche explicitement."
                        )
                    },
                }
            )
            return

    await emit({"type": "done", "payload": {"reason": "complete", "usage": usage_total}})
