"""Sessions de chat de l'agent : liste, création, historique, suppression.

Tout est scopé par ``creator_id``. Une session qu'on ne possède pas se lit
« introuvable », jamais « interdite » : la seconde réponse apprendrait à un
tiers qu'elle existe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentMessage, AgentSession
from app.services.token_meter import CARACTERES_PAR_TOKEN, TokenMeter, estimer

#: Longueur du titre dérivé du premier message.
TITRE_MAX = 80

#: Budget laissé à l'historique avant l'appel. Aucune table de fenêtres par
#: modèle : elle vieillirait plus vite qu'on ne la relit, et se tromper d'un
#: facteur deux coûte exactement ce qu'on cherche à éviter. 96 000 tient dans
#: les 128 000 devenus courants tout en laissant place au prompt système, au
#: contexte du workspace et à la réponse.
BUDGET_HISTORIQUE = 96_000

#: Budget de repli après un refus explicite du fournisseur pour cause de
#: fenêtre saturée. Assez petit pour passer chez un modèle local à 8 000, ce
#: qui évite d'avoir à connaître sa fenêtre à l'avance.
BUDGET_APRES_REFUS = 6_000

#: En deçà, élaguer un résultat d'outil ne rend presque rien et coûte du
#: contexte utile. Au-delà, un seul résultat pèse déjà plus qu'un tour entier
#: de conversation.
ELAGAGE_SEUIL = 2_000

#: Ce qu'on garde en tête d'un résultat élagué. Assez pour que le modèle
#: reconnaisse la nature de ce qu'il avait obtenu, et sache s'il doit
#: redemander.
ELAGAGE_GARDE = 600


class AgentSessionNotFoundError(LookupError):
    """Aucune session de ce créateur sous cet identifiant."""


def taille_historique(messages: list[dict[str, Any]]) -> int:
    """Coût approximatif d'un historique entier, en tokens.

    Estimation pure, sans ancre. Voir :mod:`app.services.token_meter` pour la
    mesure ancrée sur le compte réel du fournisseur.
    """
    return estimer(messages)


def _debuts_de_blocs(messages: list[dict[str, Any]]) -> list[int]:
    """Indices auxquels on peut couper sans casser une paire d'outil.

    Un message ``tool`` détaché de l'``assistant`` qui l'a demandé est rejeté
    par tous les fournisseurs. Un assistant porteur de ``tool_calls`` et les
    ``tool`` qui lui répondent forment donc un bloc indivisible.
    """
    debuts: list[int] = []
    i = 0
    n = len(messages)
    while i < n:
        debuts.append(i)
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            j = i + 1
            while j < n and messages[j].get("role") == "tool":
                j += 1
            i = j
        else:
            i += 1
    return debuts


def _elaguer_resultats(
    messages: list[dict[str, Any]], tokens_a_gagner: int, facteur: float = 1.0
) -> tuple[list[dict[str, Any]], int]:
    """Raccourcit les gros résultats d'outils, du plus ancien au plus récent.

    C'est là que sont les tokens. Un résultat d'outil monte à
    ``TOOL_RESULT_MAX`` caractères, soit plus qu'un tour entier de
    conversation ; couper des blocs de tête pour faire de la place revient à
    sacrifier les consignes du créateur pour conserver un dump JSON.

    L'élagage ne retire aucun message : les paires ``assistant``/``tool``
    restent intactes, donc aucun orphelin, et le fil de ce qui a été fait
    reste lisible. Le dernier bloc n'est jamais touché, c'est celui que le
    modèle est en train d'exploiter.

    On s'arrête dès que ``tokens_a_gagner`` est atteint : élaguer au-delà du
    nécessaire coûterait du contexte sans rien acheter. ``facteur`` traduit
    les caractères retirés dans l'échelle du fournisseur, celle qui a servi à
    calculer le manque.

    Rend la liste et le nombre de résultats élagués.
    """
    debuts = _debuts_de_blocs(messages)
    protege = debuts[-1] if debuts else len(messages)
    sortie = list(messages)
    elagues = 0
    gagnes = 0.0
    for i in range(protege):
        if gagnes >= tokens_a_gagner:
            break
        message = sortie[i]
        if message.get("role") != "tool":
            continue
        contenu = message.get("content")
        if not isinstance(contenu, str) or len(contenu) <= ELAGAGE_SEUIL:
            continue
        retires = len(contenu) - ELAGAGE_GARDE
        gagnes += retires / CARACTERES_PAR_TOKEN * facteur
        sortie[i] = {
            **message,
            "content": (
                f"{contenu[:ELAGAGE_GARDE]}\n"
                f"[Résultat tronqué pour tenir dans la fenêtre du modèle : "
                f"{retires} caractères retirés. Rappelez l'outil si vous avez "
                f"besoin de la suite ; ne devinez pas ce qu'elle contenait.]"
            ),
        }
        elagues += 1
    return (sortie, elagues) if elagues else (messages, 0)


def _message_synthese(retires: int) -> dict[str, Any]:
    """Le message qui remplace le tronçon retiré.

    Il dit au modèle qu'il lui manque quelque chose. Sans lui, le modèle
    comblerait le trou par déduction, ce qui est exactement la fabrication
    qu'on cherche à empêcher partout ailleurs.
    """
    return {
        "role": "system",
        "content": (
            f"[{retires} message(s) plus anciens de cette conversation ont été retirés "
            "pour tenir dans la fenêtre du modèle. Si un élément de ce début vous "
            "manque, demandez-le au créateur plutôt que de le supposer.]"
        ),
    }


class Compaction(NamedTuple):
    """Ce qu'a donné une passe de compaction."""

    messages: list[dict[str, Any]]
    #: Messages retirés du début de la conversation.
    retires: int
    #: Résultats d'outils raccourcis sur place.
    elagues: int


def compacter(
    messages: list[dict[str, Any]],
    budget_tokens: int,
    meter: TokenMeter | None = None,
) -> Compaction:
    """Ramène l'historique sous ``budget_tokens``, en perdant le moins possible.

    Deux leviers, dans cet ordre. D'abord l'élagage des gros résultats
    d'outils : c'est là que sont les tokens, et le raccourcir ne retire aucun
    message, donc ne coupe aucun fil. Ensuite seulement, si ça ne suffit pas,
    le retrait de blocs entiers depuis le début.

    L'ordre n'est pas cosmétique. Couper d'abord revient à sacrifier les
    consignes du créateur pour garder un dump JSON qu'on aurait pu tronquer.

    Les ``system`` de tête sont gardés : ils portent le prompt et le contexte du
    workspace, les retirer changerait le comportement de l'agent plutôt que sa
    mémoire. Le dernier bloc est gardé aussi, même s'il dépasse à lui seul :
    couper la demande en cours rendrait la réponse absurde, là où le
    dépassement, lui, reste explicable à l'utilisateur.

    ``meter`` mesure sur le compte réel du fournisseur plutôt que sur
    l'estimation. Le déclenchement et le choix du point de coupe passent par la
    même mesure : les évaluer sur deux échelles ferait couper trop peu.
    ``compacter`` le maintient cohérent avec la liste qu'il rend, l'appelant
    n'a rien à faire.

    Aucune synthèse par le modèle, à rebours du plan d'intégration : elle
    coûterait un appel dans le chemin de la requête, et surtout elle ferait
    reformuler l'historique par le modèle qui va ensuite le traiter comme un
    fait. C'est la fabrication qu'on combat partout ailleurs. Dire ce qui
    manque vaut mieux que le raconter de mémoire.
    """
    mesurer = meter.mesurer if meter is not None else estimer
    taille = mesurer(messages)
    if taille <= budget_tokens:
        return Compaction(messages, 0, 0)

    facteur = meter.facteur if meter is not None else 1.0
    messages, elagues = _elaguer_resultats(messages, taille - budget_tokens, facteur)
    if elagues and meter is not None and meter.ancre is not None:
        meter.reancrer_apres_elagage(messages[: meter.ancre.messages])
    if elagues and mesurer(messages) <= budget_tokens:
        return Compaction(messages, 0, elagues)

    tete = 0
    while tete < len(messages) and messages[tete].get("role") == "system":
        tete += 1
    systeme, corps = messages[:tete], messages[tete:]

    # Un ``tool`` en tête de bloc trahit un historique déjà bancal (lignes
    # anciennes, flux SSE interrompu) : couper là fabriquerait précisément
    # l'orphelin qu'on veut éviter.
    coupes = [i for i in _debuts_de_blocs(corps)[1:] if corps[i].get("role") != "tool"]
    if not coupes:
        return Compaction(messages, 0, elagues)

    # Retirer des messages détruit le préfixe que l'ancre décrivait, mais pas le
    # facteur qu'elle a révélé : lui est une propriété du tokeniseur. Mesurer
    # sans lui choisirait le point de coupe sur une échelle plus optimiste que
    # celle qui a déclenché la compaction, et couperait trop peu.
    recaler = meter.estimer_recale if meter is not None else estimer

    def rendre(coupe: int, reste: list[dict[str, Any]]) -> Compaction:
        if meter is not None:
            meter.oublier()
        return Compaction(reste, coupe, elagues)

    for coupe in coupes:
        reste = [*systeme, _message_synthese(coupe), *corps[coupe:]]
        if recaler(reste) <= budget_tokens:
            return rendre(coupe, reste)

    coupe = coupes[-1]
    return rendre(coupe, [*systeme, _message_synthese(coupe), *corps[coupe:]])


def titre_depuis_message(message: str) -> str:
    """Un titre lisible tiré du premier message, coupé sur un mot."""
    propre = " ".join(message.split())
    if len(propre) <= TITRE_MAX:
        return propre or "Nouvelle conversation"
    coupe = propre[:TITRE_MAX].rsplit(" ", 1)[0]
    return f"{coupe or propre[:TITRE_MAX]}…"


async def lister(db: AsyncSession, creator_id: UUID) -> list[AgentSession]:
    resultat = await db.execute(
        select(AgentSession)
        .where(AgentSession.creator_id == creator_id, AgentSession.deleted_at.is_(None))
        .order_by(AgentSession.last_message_at.desc().nullslast(), AgentSession.created_at.desc())
    )
    return list(resultat.scalars().all())


async def creer(
    db: AsyncSession,
    creator_id: UUID,
    *,
    title: str = "",
    provider_id: UUID | None = None,
    agent_slug: str | None = None,
) -> AgentSession:
    session = AgentSession(
        creator_id=creator_id,
        title=title or "Nouvelle conversation",
        provider_id=provider_id,
        agent_slug=agent_slug,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def obtenir(db: AsyncSession, creator_id: UUID, session_id: UUID) -> AgentSession:
    resultat = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.creator_id == creator_id,
            AgentSession.deleted_at.is_(None),
        )
    )
    session = resultat.scalar_one_or_none()
    if session is None:
        raise AgentSessionNotFoundError("Session introuvable.")
    return session


async def messages(db: AsyncSession, creator_id: UUID, session_id: UUID) -> list[AgentMessage]:
    await obtenir(db, creator_id, session_id)
    resultat = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at, AgentMessage.id)
    )
    return list(resultat.scalars().all())


async def ajouter_message(
    db: AsyncSession,
    session: AgentSession,
    *,
    role: str,
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> AgentMessage:
    """Ajoute un message. Append-only : aucune mise à jour d'un message existant."""
    message = AgentMessage(
        session_id=session.id,
        role=role,
        content=content or "",
        tool_calls=tool_calls,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    db.add(message)
    session.last_message_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(message)
    return message


async def usage_session(
    db: AsyncSession, creator_id: UUID, session_id: UUID
) -> dict[str, int | None]:
    """Tokens cumulés de la session : somme sur tous les messages assistant."""
    await obtenir(db, creator_id, session_id)
    row = await db.execute(
        select(
            func.sum(AgentMessage.prompt_tokens).label("total_prompt"),
            func.sum(AgentMessage.completion_tokens).label("total_completion"),
        ).where(AgentMessage.session_id == session_id)
    )
    r = row.one()
    return {
        "total_prompt_tokens": r.total_prompt or 0,
        "total_completion_tokens": r.total_completion or 0,
        "cost_eur": None,
    }


async def historique_pour_modele(
    db: AsyncSession, creator_id: UUID, session_id: UUID
) -> list[dict[str, Any]]:
    """L'historique persisté, remis dans la forme attendue par le provider."""
    rendu: list[dict[str, Any]] = []
    for message in await messages(db, creator_id, session_id):
        if message.role == "tool":
            # ``tool_call_id`` requis par la spec OpenAI ; Gemini refuse sans.
            # Lignes anciennes (avant migration 043) : nullable -> id absent ->
            # rejouera degrade sur Gemini, correct sur OpenAI/Anthropic.
            tool_msg: dict[str, Any] = {
                "role": "tool",
                "name": message.tool_name or "",
                "content": message.content,
            }
            if message.tool_call_id:
                tool_msg["tool_call_id"] = message.tool_call_id
            rendu.append(tool_msg)
        elif message.tool_calls:
            rendu.append(
                {
                    "role": message.role,
                    "content": message.content or None,
                    "tool_calls": message.tool_calls,
                }
            )
        else:
            rendu.append({"role": message.role, "content": message.content})
    return rendu


async def ancre_du_dernier_appel(
    db: AsyncSession, creator_id: UUID, session_id: UUID
) -> tuple[int, int] | None:
    """Le dernier ``prompt_tokens`` du fournisseur, et ce qu'il couvrait.

    Rend ``(nombre de messages précédents, tokens)`` dans l'ordre rendu par
    :func:`historique_pour_modele`, ou ``None`` si aucun appel de cette session
    n'a rapporté son usage. C'est ce qui permet à la compaction préventive du
    tour suivant de partir d'un compte réel plutôt que d'une estimation, alors
    même qu'aucun appel n'a encore eu lieu dans ce tour.
    """
    await obtenir(db, creator_id, session_id)
    resultat = await db.execute(
        select(AgentMessage.prompt_tokens)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at, AgentMessage.id)
    )
    jetons = list(resultat.scalars().all())
    for index in range(len(jetons) - 1, -1, -1):
        valeur = jetons[index]
        if valeur:
            return index, int(valeur)
    return None


async def mettre_a_jour(
    db: AsyncSession,
    creator_id: UUID,
    session_id: UUID,
    *,
    title: str | None = None,
    provider_id: UUID | None = None,
    model_override: str | None = None,
    agent_slug: str | None = None,
) -> AgentSession:
    """Met à jour le titre, la clé provider, le modèle et/ou l'agent d'une session.

    Seuls les champs explicitement passes (non None) sont modifies.
    Un titre vide est normalise en 'Nouvelle conversation'.
    """
    session = await obtenir(db, creator_id, session_id)
    if title is not None:
        propre = " ".join(title.split())[:TITRE_MAX]
        session.title = propre or "Nouvelle conversation"
    if provider_id is not None:
        session.provider_id = provider_id
    if model_override is not None:
        session.model_override = model_override if model_override.strip() else None
    if agent_slug is not None:
        session.agent_slug = agent_slug if agent_slug.strip() else None
    await db.commit()
    await db.refresh(session)
    return session


#: Bornes des colonnes `objectif` et `phase` (cf. migration 055).
OBJECTIF_MAX = 400
PHASE_MAX = 120


async def fixer_objectif(
    db: AsyncSession,
    creator_id: UUID,
    session_id: UUID,
    *,
    objectif: str | None = None,
    phase: str | None = None,
) -> AgentSession:
    """Pose l'objectif et/ou la phase courante d'une session.

    Séparé de :func:`mettre_a_jour` : celui-là sert le formulaire humain, celui-ci
    l'agent en cours de tour. Les mélanger ferait qu'un objectif posé par le
    modèle emprunterait le chemin qui normalise un titre vide en « Nouvelle
    conversation ».
    """
    session = await obtenir(db, creator_id, session_id)
    if objectif is not None:
        propre = " ".join(objectif.split())[:OBJECTIF_MAX]
        session.objectif = propre or None
    if phase is not None:
        propre = " ".join(phase.split())[:PHASE_MAX]
        session.phase = propre or None
    await db.commit()
    await db.refresh(session)
    return session


async def objectif_courant(
    db: AsyncSession, creator_id: UUID, session_id: UUID
) -> tuple[str | None, str | None]:
    """L'objectif et la phase d'une session, ou ``(None, None)``.

    Ne lève pas : une session introuvable rend simplement l'absence d'objectif.
    Le prompt système doit s'assembler même quand cette lecture échoue.
    """
    try:
        session = await obtenir(db, creator_id, session_id)
    except Exception:  # noqa: BLE001 — l'absence d'objectif n'est pas une erreur ici
        return None, None
    return session.objectif, session.phase


async def supprimer(db: AsyncSession, creator_id: UUID, session_id: UUID) -> None:
    """Suppression logique : la trace reste, la session sort des listes."""
    session = await obtenir(db, creator_id, session_id)
    session.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
