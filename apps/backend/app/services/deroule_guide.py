"""Deroule guide d'une fiche sujet, pilote par le serveur.

Mesure du 2026-09-13 (conversations « arthrose ») : laisse libre, l'agent
repondait de memoire, posait des sources sans extrait, reformulait les
verbatims et ne cherchait jamais ce qui nuance. Les outils de deroule
(`fiche_etapes`, `fiche_state`) n'ont pas ete appeles une seule fois : un petit
modele ne decouvre pas seul un deroule decrit dans un fichier.

Ici le serveur tient l'ordre. Une question devient une fiche sujet par etapes,
et chaque etape est une boucle d'agent qui ne voit que ses outils :

1. cadrage : si la question admet des angles tres differents, le modele pose
   une question a choix au createur (`demander_precision`), et sa reponse
   guide la suite (Open Deep Research, Morphic) ;
2. plan : la fiche existante ou creee, et ses sous-questions (`definir_plan`).
   Le plan est montre au createur, qui peut le corriger avant la recherche
   (Perplexity Deep Research, Gemini, Scira) ;
3. exploration, une boucle d'agent par sous-question : `rechercher` execute la
   methode de recherche cote serveur (`services/recherche_approfondie.py`) et
   rend des passages exacts ; l'agent pose ceux qui repondent avec
   `add_source`. Elle tourne par passes : tant qu'une passe couvre une
   sous-question jusque-la vide et qu'il en reste, la suivante relance celles
   qui restent avec d'autres formulations. Aucun nombre de passes fixe
   d'avance : une passe qui ne couvre rien de neuf arrete l'exploration ;
4. positions : `update_source`, qui exige deja un extrait. Suit une relecture :
   la grille de `services/relecture.py` nomme les manques (source sans
   extrait, sans position, aucune nuance, retractation en appui), et les etapes
   qui les comblent sont relancees tant qu'une relecture en comble au moins un ;
5. bilan : la reponse au createur, tiree des seuls extraits poses, chaque
   phrase renvoyant a l'extrait qui la soutient ; les renvois sont verifies et
   deviennent des liens (`services/citations_bilan.py`), et des sous-questions
   de suite sont proposees (`proposer_suites`).

Le mode rapide garde la methode et retire les budgets : ni cadrage, ni plan a
valider, une seule passe, ni suivi des citations, ni relecture. Une suite
prolonge une fiche existante par une sous-question : ni cadrage ni plan.

Une boucle par sous-question donne a chaque recherche son propre budget de
temps et un contexte court, lisible par un petit modele. Le compte rendu de
chaque etape sert de contexte a la suivante. Le deroule tourne dans le tour
detache du chat : reprise apres une coupure, fiche en direct et bouton
« Arrêter » restent ceux de la conversation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.registry import construire_registre, filtrer
from app.agent_tools.tool import AgentTool
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.services import agent_approvals, citations_bilan, couverture, relecture
from app.services.agent import Approuver, Emitter, boucle
from app.services.agent_definitions import AgentDefinition
from app.services.couverture import Couverture
from app.services.options_recherche import Options
from app.services.relecture import Manque

logger = logging.getLogger(__name__)

#: Attend la reponse du createur a une question du deroule, par son identifiant.
#: `None` : pas de reponse (delai, ou personne pour repondre), le deroule continue.
Attendre = Callable[[str], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class Etape:
    id: str
    titre: str
    outils: tuple[str, ...]
    consigne: str


@dataclass(frozen=True)
class Suite:
    """Prolonger une fiche existante par une sous-question."""

    card_slug: str
    sous_question: str


_CONSIGNE_COMMUNE = (
    "Tu déroules une étape de la création d'une fiche sujet Philum. Fais seulement "
    "ce que l'étape demande, avec les outils qu'elle te donne, puis termine par le "
    "compte rendu qu'elle demande. N'invente ni adresse, ni fait, ni verbatim."
)

ETAPES: tuple[Etape, ...] = (
    Etape(
        id="cadrage",
        titre="Cadrage",
        outils=("demander_precision",),
        consigne=(
            "1. Lis la question du créateur. Si elle admet des angles très différents qui "
            "mèneraient à des fiches différentes (public visé, période, lieu, sens d'un "
            "terme, portée), appelle demander_precision(question, options) avec ces angles, "
            "chacun en une phrase courte.\n"
            "2. Si la question est claire, n'appelle aucun outil.\n"
            "3. Termine en une phrase : l'angle que la fiche prendra, ou la précision "
            "demandée."
        ),
    ),
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
        outils=("get_my_card", "proposer_suites"),
        consigne=(
            "1. Appelle d'abord proposer_suites(questions) avec des sous-questions que la "
            "fiche ne couvre pas encore et qui la prolongeraient.\n"
            "2. Puis réponds au créateur en t'appuyant uniquement sur les extraits posés, "
            "rangés ci-dessus par sous-question avec leur identifiant :\n"
            "   - un titre « ## » par sous-question qui a des extraits, puis ce que disent "
            "ces extraits, ce qui appuie comme ce qui nuance ;\n"
            "   - chaque phrase qui s'appuie sur un extrait finit par [extrait:<id>] de cet "
            "extrait, ou de plusieurs ; n'écris rien qu'aucun extrait ne soutient ;\n"
            "   - ce qui manque encore (sous-questions sans extrait, manques de la "
            "relecture) et les limites.\n"
            "Pas de plan, pas d'annonce de ce que tu vas faire."
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

#: Outils d'interaction : le deroule lit leurs arguments et agit lui-meme.
_OUTILS_D_INTERACTION = frozenset({"demander_precision", "proposer_suites"})

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


#: Longueur d'un extrait montre dans la consigne du bilan. Borne de lisibilite de
#: la consigne : l'identifiant suffit a citer, le debut du passage a le reconnaitre.
_EXTRAIT_MONTRE = 300


def _bloc_extraits(groupes: list[tuple[str, list[couverture.ExtraitRange]]]) -> str:
    if not any(extraits for _q, extraits in groupes):
        return ""
    morceaux = ["Extraits de la fiche, rangés par sous-question (identifiant, puis passage) :"]
    for question, extraits in groupes:
        if not extraits:
            continue
        morceaux.append(f"# {question}")
        for e in extraits:
            passage = (
                e.texte if len(e.texte) <= _EXTRAIT_MONTRE else e.texte[:_EXTRAIT_MONTRE] + "…"
            )
            morceaux.append(f"- [extrait:{e.id}] « {passage} » ({e.source})")
    return "\n".join(morceaux)


async def _extraits_ranges(
    db: AsyncSession, user: User, slug: str | None
) -> list[tuple[str, list[couverture.ExtraitRange]]]:
    if not slug:
        return []
    try:
        return await couverture.extraits_par_sous_question(db, user.id, slug)
    except Exception:  # noqa: BLE001  # le rangement guide le bilan, il ne bloque jamais le deroule
        logger.warning("Extraits illisibles pour %s", slug, exc_info=True)
        return []


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
    options: Options | None = None,
    suite: Suite | None = None,
    attendre: Attendre | None = None,
    decalage_initial: int = 0,
) -> None:
    """Deroule les etapes, et verse le fil du tour dans `ajouts`.

    `ajouts` et `heures` sont remplis au fil des etapes plutot que rendus : un
    tour arrete en cours d'etape doit laisser en base ce qui a deja ete ecrit.
    Les numeros de tour des evenements sont decales d'une etape a l'autre, pour
    que la reponse finale reste le texte du dernier appel au modele.

    `attendre` recoit les reponses du createur aux questions du deroule ; sans
    lui (banc, tests), aucune pause : les questions ne sont pas posees.
    """
    registre = registre or construire_registre()
    options = options or Options()
    comptes_rendus: list[str] = []
    etat: dict[str, Any] = {
        "slug": suite.card_slug if suite else None,
        "decalage": decalage_initial,
        "texte": "",
        "interactions": {},
    }
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
        appels: dict[str, dict[str, Any]] = {}

        async def capter(
            event: dict[str, Any],
            _textes: dict[int, list[str]] = textes,
            _echec: list[str] = echec,
            _appels: dict[str, dict[str, Any]] = appels,
        ) -> None:
            genre = event.get("type")
            charge = event.get("payload") or {}
            if isinstance(charge.get("tour"), int):
                charge = {**charge, "tour": etat["decalage"] + charge["tour"]}
                event = {**event, "payload": charge}
            if genre == "message_delta":
                _textes.setdefault(charge["tour"], []).append(charge["delta"])
            elif genre == "tool_call":
                nom = str(charge.get("name"))
                champ = _OUTILS_QUI_NOMMENT_LA_FICHE.get(nom)
                valeur = (charge.get("arguments") or {}).get(champ) if champ else None
                if isinstance(valeur, str) and valeur.strip() and etat["slug"] is None:
                    etat["slug"] = valeur.strip()
                if nom in _OUTILS_D_INTERACTION:
                    _appels[nom] = dict(charge.get("arguments") or {})
            elif genre == "tool_result":
                nom = str(charge.get("name"))
                resultat = charge.get("result") or {}
                if nom == "create_card":
                    slug = resultat.get("slug")
                    if isinstance(slug, str) and slug:
                        etat["slug"] = slug
                if nom in _OUTILS_D_INTERACTION and nom in _appels:
                    if "error" in resultat:
                        _appels.pop(nom)
                    else:
                        etat["interactions"][nom] = _appels[nom]
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
        etat["texte"] = compte_rendu
        if rang < len(ETAPES) and compte_rendu:
            ajouts.append({"role": "assistant", "content": compte_rendu})
            heures.append(datetime.now(UTC).replace(tzinfo=None))
            comptes_rendus.append(f"## {titre}\n{compte_rendu}")
        return True

    async def poser(genre: str, charge: dict[str, Any]) -> dict[str, Any] | None:
        """Pose une question au createur et attend sa reponse. None sans reponse."""
        if attendre is None:
            return None
        request_id = uuid4().hex
        await emit(
            {
                "type": "question_guidee",
                "payload": {
                    "request_id": request_id,
                    "genre": genre,
                    "expires_at": time.time() + agent_approvals.DELAI_MAX,
                    **charge,
                },
            }
        )
        reponse = await attendre(request_id)
        await emit(
            {
                "type": "question_resolue",
                "payload": {"request_id": request_id, "reponse": reponse},
            }
        )
        return reponse

    async def cadrer() -> None:
        precision = etat["interactions"].pop("demander_precision", None)
        if not precision:
            return
        reponse = await poser(
            "precision",
            {"question": precision.get("question"), "options": precision.get("options") or []},
        )
        choix = " ".join(str((reponse or {}).get("choix") or "").split())
        comptes_rendus.append(
            f"## Précision du créateur\n{choix}"
            if choix
            else "## Précision du créateur\nPas de réponse : prends l'angle le plus large, "
            "et dis-le au bilan."
        )

    async def valider_plan() -> None:
        slug = etat["slug"]
        if not slug or attendre is None:
            return
        plan = await couverture.lire_plan(db, user.id, slug)
        if not plan:
            return
        reponse = await poser(
            "plan",
            {
                "question": "Voici le plan de la fiche. Corrigez-le, ou lancez la recherche.",
                "sous_questions": plan,
            },
        )
        corrigees = [" ".join(str(q).split()) for q in (reponse or {}).get("sous_questions") or []]
        corrigees = [q for q in corrigees if q]
        if not corrigees or corrigees == plan:
            return
        try:
            retenues = await couverture.ecrire_plan(db, user.id, slug, corrigees)
            await db.commit()
        except ValueError:
            return
        comptes_rendus.append(
            "## Plan corrigé par le créateur\n" + "\n".join(f"- {q}" for q in retenues)
        )

    async def explorer(etape: Etape, rang: int) -> bool:
        """Une boucle par sous-question, par passes, tant qu'une passe couvre du neuf."""
        avant = await _couverture(db, user, etat["slug"])
        passe = 1
        while True:
            if suite is not None:
                cibles = [suite.sous_question] if passe == 1 else []
            elif passe == 1:
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
            # Mode rapide et suite : une seule passe, sur ce qui a ete demande.
            if options.rapide or suite is not None:
                return True
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

    async def conclure() -> None:
        """Lie les renvois du bilan aux extraits, et propose les suites."""
        slug = etat["slug"]
        texte = etat["texte"]
        if slug and texte and citations_bilan.RENVOI.search(texte):
            try:
                lie = await citations_bilan.lier(db, user.id, user.username, slug, texte)
            except Exception:  # noqa: BLE001  # un lien rate ne doit pas perdre la reponse
                logger.warning("Renvois du bilan illisibles pour %s", slug, exc_info=True)
            else:
                await emit(
                    {
                        "type": "reponse_verifiee",
                        "payload": {"texte": lie.texte, "cites": lie.cites, "retires": lie.retires},
                    }
                )
        suites = etat["interactions"].pop("proposer_suites", None)
        questions = [
            " ".join(str(q).split())
            for q in (suites or {}).get("questions") or []
            if str(q).strip()
        ]
        if slug and questions:
            await emit(
                {"type": "suites_proposees", "payload": {"card_slug": slug, "questions": questions}}
            )

    if suite is not None:
        if await _couverture(db, user, suite.card_slug) is None:
            await emit(
                {
                    "type": "error",
                    "payload": {"message": f"La fiche « {suite.card_slug} » est introuvable."},
                }
            )
            return
        plan = await couverture.lire_plan(db, user.id, suite.card_slug)
        if suite.sous_question not in plan:
            await couverture.ecrire_plan(db, user.id, suite.card_slug, [*plan, suite.sous_question])
            await db.commit()

    for rang, etape in enumerate(ETAPES, start=1):
        if etape.id in ("cadrage", "plan") and (
            suite is not None or (options.rapide and etape.id == "cadrage")
        ):
            continue
        if etape.id == "exploration":
            if not await explorer(etape, rang):
                return
        else:
            supplement = _bloc_couverture(await _couverture(db, user, etat["slug"]))
            if etape.id == "bilan":
                restants = _bloc_restants(await _grille(db, user, etat["slug"]))
                # Les citations rangees par sous-question avant d'ecrire, comme Ai2
                # Scholar QA : la reponse se redige depuis ces extraits et leurs
                # identifiants, pas depuis la memoire du modele.
                extraits = _bloc_extraits(await _extraits_ranges(db, user, etat["slug"]))
                supplement = "\n\n".join(b for b in (extraits, supplement, restants) if b)
            if not await executer(etape, rang, etape.titre, supplement, None):
                return
        if etape.id == "cadrage":
            await cadrer()
        if etape.id == "plan":
            if not etat["slug"]:
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
            if not options.rapide:
                await valider_plan()
        if etape.id == "positions" and not options.rapide and not await relire():
            return
        if etape.id == "bilan":
            await conclure()

    await emit({"type": "done", "payload": {"reason": "complete", "usage": usage_total}})


async def converser_ou_derouler(
    db: AsyncSession,
    user: User,
    provider: AgentProvider,
    messages: list[dict[str, Any]],
    emit: Emitter,
    approuver: Approuver,
    ajouts: list[dict[str, Any]],
    heures: list[datetime],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    modele: str | None = None,
    agent_def: AgentDefinition | None = None,
    ancre_tokens: tuple[int, int] | None = None,
    session_id: UUID | None = None,
    replis: list[AgentProvider] | None = None,
    registre: dict[str, AgentTool] | None = None,
    options: Options | None = None,
    attendre: Attendre | None = None,
) -> bool:
    """La conversation, et le deroule guide quand l'agent decide qu'une question appelle une fiche.

    Une liste de mots interrogatifs francais decidait avant : une question en
    anglais, une forme affirmative ou un second message passaient a cote. Comme
    Vane (classifieur) et Scira (routeur), c'est desormais le modele qui decide,
    dans toutes les langues : il appelle `demarrer_fiche_sujet(question)`, et le
    deroule prend la suite dans le meme tour, sans appel de plus quand il n'y a
    rien a documenter.

    L'outil est ajoute a tout agent : lancer une fiche est une capacite du chat.
    Rend vrai quand le deroule a tourne ; ses messages vont dans `ajouts`, ceux
    de la conversation restent dans `messages`.
    """
    from dataclasses import replace

    from app.agent_tools.deroule import OUTIL_DEMARRAGE

    if agent_def is not None and OUTIL_DEMARRAGE not in agent_def.tools:
        agent_def = replace(agent_def, tools=(*agent_def.tools, OUTIL_DEMARRAGE))
    questions: list[str] = []
    en_attente: dict[str, str] = {}
    fins: list[dict[str, Any]] = []
    etat = {"tour": 0, "interrompu": False}

    async def capter(event: dict[str, Any]) -> None:
        genre = event.get("type")
        charge = event.get("payload") or {}
        if isinstance(charge.get("tour"), int):
            etat["tour"] = max(int(etat["tour"]), charge["tour"])
        if genre == "tool_call" and charge.get("name") == OUTIL_DEMARRAGE:
            en_attente["question"] = " ".join(
                str((charge.get("arguments") or {}).get("question") or "").split()
            )
        elif genre == "tool_result" and charge.get("name") == OUTIL_DEMARRAGE:
            if "error" not in (charge.get("result") or {}) and en_attente.get("question"):
                questions.append(en_attente["question"])
        elif genre == "done":
            # Retenu : si le deroule prend la suite, c'est sa fin qui clot le tour.
            fins.append(event)
            return
        elif genre in ("error", "continuation"):
            etat["interrompu"] = True
        await emit(event)

    await boucle(
        db,
        user,
        provider,
        messages,
        capter,
        approuver,
        transport=transport,
        registre=registre,
        modele=modele,
        agent_def=agent_def,
        ancre_tokens=ancre_tokens,
        session_id=session_id,
        replis=replis,
    )
    if not questions or etat["interrompu"]:
        for event in fins:
            await emit(event)
        return False
    await derouler(
        db,
        user,
        provider,
        questions[-1],
        emit,
        approuver,
        ajouts,
        heures,
        transport=transport,
        modele=modele,
        session_id=session_id,
        replis=replis,
        registre=registre,
        options=options,
        attendre=attendre,
        decalage_initial=int(etat["tour"]),
    )
    return True
