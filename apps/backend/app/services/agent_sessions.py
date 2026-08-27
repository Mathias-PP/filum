"""Sessions de chat de l'agent : liste, création, historique, suppression.

Tout est scopé par ``creator_id``. Une session qu'on ne possède pas se lit
« introuvable », jamais « interdite » : la seconde réponse apprendrait à un
tiers qu'elle existe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentMessage, AgentSession
from app.services.token_meter import TokenMeter, estimer

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


def compacter(
    messages: list[dict[str, Any]],
    budget_tokens: int,
    meter: TokenMeter | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Ramène l'historique sous ``budget_tokens``, du plus ancien au plus récent.

    Les ``system`` de tête sont gardés : ils portent le prompt et le contexte du
    workspace, les retirer changerait le comportement de l'agent plutôt que sa
    mémoire. Le dernier bloc est gardé aussi, même s'il dépasse à lui seul :
    couper la demande en cours rendrait la réponse absurde, là où le
    dépassement, lui, reste explicable à l'utilisateur.

    ``meter`` mesure sur le compte réel du fournisseur plutôt que sur
    l'estimation. Le déclenchement et le choix du point de coupe passent par la
    même mesure : les évaluer sur deux échelles ferait couper trop peu.

    Rend la liste compactée et le nombre de messages retirés, 0 si rien.
    """
    mesurer = meter.mesurer if meter is not None else estimer
    if mesurer(messages) <= budget_tokens:
        return messages, 0

    tete = 0
    while tete < len(messages) and messages[tete].get("role") == "system":
        tete += 1
    systeme, corps = messages[:tete], messages[tete:]

    # Un ``tool`` en tête de bloc trahit un historique déjà bancal (lignes
    # anciennes, flux SSE interrompu) : couper là fabriquerait précisément
    # l'orphelin qu'on veut éviter.
    coupes = [i for i in _debuts_de_blocs(corps)[1:] if corps[i].get("role") != "tool"]
    if not coupes:
        return messages, 0

    for coupe in coupes:
        reste = [*systeme, _message_synthese(coupe), *corps[coupe:]]
        if mesurer(reste) <= budget_tokens:
            return reste, coupe

    coupe = coupes[-1]
    return [*systeme, _message_synthese(coupe), *corps[coupe:]], coupe


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


async def supprimer(db: AsyncSession, creator_id: UUID, session_id: UUID) -> None:
    """Suppression logique : la trace reste, la session sort des listes."""
    session = await obtenir(db, creator_id, session_id)
    session.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
