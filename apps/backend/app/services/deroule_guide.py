"""Deroule guide d'une fiche sujet, pilote par le serveur.

Mesure du 2026-09-13 (conversations « arthrose ») : laisse libre, l'agent
repondait de memoire, posait des sources sans extrait, reformulait les
verbatims et ne cherchait jamais ce qui nuance. Les outils de deroule
(`fiche_etapes`, `fiche_state`) n'ont pas ete appeles une seule fois : un petit
modele ne decouvre pas seul un deroule decrit dans un fichier.

Ici le serveur tient l'ordre. Une question devient une fiche sujet par etapes,
et chaque etape est une boucle d'agent qui ne voit que ses outils :

1. plan : la fiche existante ou creee, et ses sous-questions (`definir_plan`) ;
2. exploration, une boucle d'agent par sous-question : `rechercher` execute la
   methode de recherche cote serveur (`services/recherche_approfondie.py`) et
   rend des passages exacts ; l'agent pose ceux qui repondent avec
   `add_source`. Elle tourne par passes : tant qu'une passe couvre une
   sous-question jusque-la vide et qu'il en reste, la suivante relance celles
   qui restent avec d'autres formulations. Aucun nombre de passes fixe
   d'avance : une passe qui ne couvre rien de neuf arrete l'exploration ;
3. positions : `update_source`, qui exige deja un extrait. Suit une relecture :
   la grille de `services/relecture.py` nomme les manques (source sans
   extrait, sans position, aucune nuance, retractation en appui), et les etapes
   qui les comblent sont relancees tant qu'une relecture en comble au moins un ;
4. bilan : la reponse au createur, tiree des seuls extraits poses, avec ce qui
   manque encore.

Une boucle par sous-question donne a chaque recherche son propre budget de
temps et un contexte court, lisible par un petit modele.

Le compte rendu de chaque etape sert de contexte a la suivante. Le deroule
tourne dans le tour detache du chat : reprise apres une coupure, fiche en
direct et bouton « Arrêter » restent ceux de la conversation.
"""

from __future__ import annotations

import logging
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
from app.services import couverture, relecture
from app.services.agent import Approuver, Emitter, boucle
from app.services.agent_definitions import AgentDefinition
from app.services.couverture import Couverture
from app.services.relecture import Manque

logger = logging.getLogger(__name__)

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
#: documenter : le deroule ne doit pas la reduire a des etapes fixes.
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
        id="plan",
        titre="Plan",
        outils=("list_my_cards", "get_my_card", "create_card", "definir_plan"),
        consigne=(
            "1. Appelle list_my_cards. Si une fiche porte déjà ce sujet, appelle "
            "get_my_card avec son slug et ne crée rien.\n"
            "2. Sinon, crée une fiche sujet avec create_card(card_kind='sujet'). Le "
            "titre reprend la question.\n"
            "3. Appelle definir_plan(slug, sous_questions) : décompose la question en "
            "sous-questions, une par aspect distinct qu'une réponse complète doit "
            "traiter (par exemple causes, mécanismes, effets mesurés, limites, "
            "contexte historique ou juridique, controverses). Autant de sous-questions "
            "que la question en appelle, chacune assez précise pour qu'une source "
            "puisse l'éclairer.\n"
            "4. Termine par le slug de la fiche, puis les sous-questions, une par ligne."
        ),
    ),
    Etape(
        id="exploration",
        titre="Exploration",
        outils=(
            "rechercher",
            "suite_recherche",
            "add_source",
            "add_excerpt",
            "list_sources",
            "find_passage",
        ),
        consigne=(
            "1. Appelle rechercher(card_slug, sous_question, requetes, "
            "requetes_contradiction) pour la sous-question travaillée.\n"
            "   - requetes : plusieurs formulations qui diffèrent vraiment : vocabulaire "
            "technique du domaine, synonymes, noms de mesures, d'études ou "
            "d'institutions, et les langues dans lesquelles ce sujet est étudié.\n"
            "   - requetes_contradiction : des formulations qui cherchent ce qui contredit ou "
            "nuance le propos dominant (limites, critiques, résultats contraires). Si rien "
            "n'est trouvé, dis-le et continue : cela ne bloque pas.\n"
            "2. Pour chaque source rendue, garde les passages qui répondent vraiment à la "
            "sous-question ou la nuancent ; écarte ceux qui ne font que l'effleurer.\n"
            "3. Source nouvelle : add_source(card_slug, url, metadata_from='page', "
            'excerpts=[{"text": passage recopié tel quel, "context": ce que le passage '
            "établit}]), avec l'url rendue par rechercher et sans position. Source déjà "
            "sur la fiche (source_id rendu) : add_excerpt(source_id, text) pour chaque "
            "passage retenu.\n"
            "4. Une source dont aucun passage ne répond n'est pas ajoutée.\n"
            "5. Si le résultat annonce une page suivante, appelle suite_recherche et "
            "traite-la de même.\n"
            "Termine par : les sources ajoutées avec leur nombre d'extraits, les sources "
            "écartées avec la raison, puis la raison de l'arrêt de la recherche et "
            "l'estimation de ce qui reste, telles que le journal les donne."
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
            "1. la réponse à la question, sous-question par sous-question ;\n"
            "2. ce qui la nuance ;\n"
            "3. ce qui manque encore : sous-questions sans extrait, manques de la "
            "relecture, passages qui n'ont pas pu être cités ;\n"
            "4. les limites.\n"
            "N'ajoute rien qui ne soit dans un extrait. Pas de plan, pas d'annonce de "
            "ce que tu vas faire."
        ),
    ),
)

_ETAPE_PAR_ID = {etape.id: etape for etape in ETAPES}
_RANG_PAR_ID = {etape.id: rang for rang, etape in enumerate(ETAPES, start=1)}

#: Outils dont les arguments nomment la fiche travaillee.
_OUTILS_QUI_NOMMENT_LA_FICHE = {
    "get_my_card": "slug",
    "add_source": "card_slug",
    "definir_plan": "slug",
    "rechercher": "card_slug",
}

#: Ce que l'etape doit faire de chaque manque, dit au modele.
_CONSIGNE_PAR_MANQUE = {
    relecture.SOURCE_SANS_EXTRAIT: (
        "source sans extrait : cherche ses passages avec find_passage puis pose-les avec "
        "add_excerpt ; si aucun ne répond à la question, dis-le"
    ),
    relecture.SANS_NUANCE: (
        "aucune source ne nuance la réponse : appelle rechercher avec la question de la "
        "fiche pour sous_question et des requetes_contradiction variées (limites, "
        "critiques, résultats contraires, dans les langues où le sujet est étudié), puis "
        "pose les passages qui nuancent"
    ),
    relecture.SOURCE_SANS_POSITION: (
        "source citée sans position : pose sa position avec update_source"
    ),
    relecture.RETRACTATION: (
        "source rétractée posée en appui : passe-la en stance='contexte' avec update_source"
    ),
}

#: Libelle court de chaque manque, pour le bilan.
_LIBELLE_MANQUE = {
    relecture.SOUS_QUESTION_VIDE: "sous-question sans extrait",
    relecture.SOURCE_SANS_EXTRAIT: "source sans extrait",
    relecture.SOURCE_SANS_POSITION: "source sans position",
    relecture.POSITION_SANS_APPUI: "position sans extrait qui la justifie",
    relecture.SANS_NUANCE: "aucune source qui nuance",
    relecture.RETRACTATION: "source rétractée en appui",
}


def relancer_une_passe(avant: Couverture | None, apres: Couverture | None) -> bool:
    """Une nouvelle passe d'exploration vaut-elle d'etre lancee ?

    Oui tant qu'il reste des sous-questions vides et que la derniere passe en a
    couvert au moins une qui l'etait. Chaque passe relancee couvre donc une
    sous-question de plus : l'exploration finit, sans nombre de passes fixe.
    Sans plan, une seule passe.
    """
    if avant is None or apres is None:
        return False
    vides_avant = set(avant.vides())
    vides_apres = set(apres.vides())
    return bool(vides_apres) and bool(vides_avant - vides_apres)


def _comblables(manques: list[Manque]) -> list[Manque]:
    return [m for m in manques if m.genre in relecture.COMBLABLES]


def _bloc_couverture(etat: Couverture | None) -> str:
    if etat is None or not etat.sous_questions:
        return ""
    lignes = [
        f"- {q.texte} : {q.extraits} extrait{'s' if q.extraits > 1 else ''}"
        for q in etat.sous_questions
    ]
    return "Plan de la fiche, et extraits déjà posés par sous-question :\n" + "\n".join(lignes)


def _bloc_sous_question(sous_question: str, *, relance: bool) -> str:
    bloc = f"Sous-question travaillée : {sous_question}"
    if relance:
        # La replanification de Gemini Deep Research, tenue par le serveur : ce
        # qui n'a rien donne se cherche autrement, pas une seconde fois pareil.
        bloc += (
            "\nLes recherches précédentes n'ont posé aucun extrait pour elle. Formule "
            "autrement : autre vocabulaire, autre discipline qui étudie le même phénomène, "
            "autre langue, ou la même question redéfinie. Les sources déjà ajoutées n'ont "
            "pas à être reprises."
        )
    return bloc


def _bloc_manques(manques: list[Manque]) -> str:
    lignes = [f"- {_CONSIGNE_PAR_MANQUE[m.genre]} : {m.cible}" for m in manques]
    return (
        "La relecture de la fiche a trouvé ces manques. Traite-les, et seulement eux :\n"
        + "\n".join(lignes)
    )


def _bloc_restants(manques: list[Manque]) -> str:
    if not manques:
        return ""
    lignes = [f"- {_LIBELLE_MANQUE.get(m.genre, m.genre)} : {m.cible}" for m in manques]
    return "Ce qui manque encore à la fiche, à dire au créateur :\n" + "\n".join(lignes)


async def _couverture(db: AsyncSession, user: User, slug: str | None) -> Couverture | None:
    if not slug:
        return None
    try:
        return await couverture.calculer(db, user.id, slug)
    except Exception:  # noqa: BLE001  # la couverture guide, elle ne bloque jamais le deroule
        logger.warning("Couverture illisible pour %s", slug, exc_info=True)
        return None


async def _grille(db: AsyncSession, user: User, slug: str | None) -> list[Manque]:
    if not slug:
        return []
    try:
        return await relecture.grille(db, user.id, slug)
    except Exception:  # noqa: BLE001  # la relecture guide, elle ne bloque jamais le deroule
        logger.warning("Relecture illisible pour %s", slug, exc_info=True)
        return []


def _consigne(
    etape: Etape,
    rang: int,
    titre: str,
    question: str,
    slug: str | None,
    contexte: str,
    supplement: str,
) -> str:
    morceaux = [
        f"Étape {rang} sur {len(ETAPES)} : {titre}.",
        f"Question du créateur : {question}",
    ]
    if slug:
        morceaux.append(f"Fiche travaillée : {slug}")
    if contexte:
        morceaux.append(f"Ce que les étapes précédentes ont produit :\n{contexte}")
    if supplement:
        morceaux.append(supplement)
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
    """Deroule les etapes, et verse le fil du tour dans `ajouts`.

    `ajouts` et `heures` sont remplis au fil des etapes plutot que rendus : un
    tour arrete en cours d'etape doit laisser en base ce qui a deja ete ecrit.
    Les numeros de tour des evenements sont decales d'une etape a l'autre, pour
    que la reponse finale reste le texte du dernier appel au modele.
    """
    registre = registre or construire_registre()
    comptes_rendus: list[str] = []
    etat: dict[str, Any] = {"slug": None, "decalage": 0}
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}

    async def executer(
        etape: Etape, rang: int, titre: str, supplement: str, passe: int | None
    ) -> bool:
        """Une boucle d'agent pour une etape. Faux quand le deroule doit s'arreter."""
        charge_etape: dict[str, Any] = {
            "etape": etape.id,
            "titre": titre,
            "rang": rang,
            "total": len(ETAPES),
        }
        if passe is not None:
            charge_etape["passe"] = passe
        await emit({"type": "etape_guidee", "payload": charge_etape})
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
                    etape,
                    rang,
                    titre,
                    question,
                    etat["slug"],
                    "\n\n".join(comptes_rendus),
                    supplement,
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
            return False
        if textes:
            etat["decalage"] = max(textes)
        compte_rendu = "".join(textes[max(textes)]).strip() if textes else ""
        if rang < len(ETAPES) and compte_rendu:
            ajouts.append({"role": "assistant", "content": compte_rendu})
            heures.append(datetime.now(UTC).replace(tzinfo=None))
            comptes_rendus.append(f"## {titre}\n{compte_rendu}")
        return True

    async def explorer(etape: Etape, rang: int) -> bool:
        """Une boucle par sous-question, par passes, tant qu'une passe couvre du neuf."""
        avant = await _couverture(db, user, etat["slug"])
        passe = 1
        while True:
            if passe == 1:
                plan = [q.texte for q in avant.sous_questions] if avant else []
                cibles = plan or [question]
            else:
                cibles = avant.vides() if avant else []
            for sous_question in cibles:
                titre = f"{etape.titre} : {sous_question}"
                if passe > 1:
                    titre += f", passe {passe}"
                supplement = "\n\n".join(
                    b
                    for b in (
                        _bloc_couverture(avant),
                        _bloc_sous_question(sous_question, relance=passe > 1),
                    )
                    if b
                )
                if not await executer(etape, rang, titre, supplement, passe):
                    return False
            apres = await _couverture(db, user, etat["slug"])
            if not relancer_une_passe(avant, apres):
                return True
            avant, passe = apres, passe + 1

    async def relire() -> bool:
        """Relance les etapes qui comblent les manques, tant qu'une relecture en comble.

        Chaque tour relance doit avoir fait baisser le nombre de manques
        comblables : la relecture finit, sans nombre de tours fixe d'avance.
        """
        avant = _comblables(await _grille(db, user, etat["slug"]))
        tour = 1
        while avant:
            a_explorer = [m for m in avant if m.etape == "exploration"]
            if a_explorer:
                etape = _ETAPE_PAR_ID["exploration"]
                titre = f"Relecture {tour}, exploration"
                if not await executer(
                    etape, _RANG_PAR_ID[etape.id], titre, _bloc_manques(a_explorer), None
                ):
                    return False
            a_positionner = [m for m in avant if m.etape == "positions"]
            # Une exploration de relecture a pu poser des sources : elles attendent
            # leur position meme si la grille d'avant ne les connaissait pas.
            if a_positionner or a_explorer:
                etape = _ETAPE_PAR_ID["positions"]
                titre = f"Relecture {tour}, positions"
                supplement = _bloc_manques(a_positionner) if a_positionner else ""
                if not await executer(etape, _RANG_PAR_ID[etape.id], titre, supplement, None):
                    return False
            apres = _comblables(await _grille(db, user, etat["slug"]))
            if len(apres) >= len(avant):
                return True
            avant, tour = apres, tour + 1
        return True

    for rang, etape in enumerate(ETAPES, start=1):
        if etape.id == "exploration":
            if not await explorer(etape, rang):
                return
        else:
            supplement = _bloc_couverture(await _couverture(db, user, etat["slug"]))
            if etape.id == "bilan":
                restants = _bloc_restants(await _grille(db, user, etat["slug"]))
                supplement = "\n\n".join(b for b in (supplement, restants) if b)
            if not await executer(etape, rang, etape.titre, supplement, None):
                return
        if etape.id == "plan" and not etat["slug"]:
            await emit(
                {
                    "type": "error",
                    "payload": {
                        "message": (
                            "Aucune fiche n'a été créée ni retenue à l'étape du plan : "
                            "le déroulé guidé s'arrête là. Reformulez la question, ou "
                            "demandez la fiche explicitement."
                        )
                    },
                }
            )
            return
        if etape.id == "positions" and not await relire():
            return

    await emit({"type": "done", "payload": {"reason": "complete", "usage": usage_total}})
