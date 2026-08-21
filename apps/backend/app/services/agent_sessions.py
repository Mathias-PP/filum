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

#: Longueur du titre dérivé du premier message.
TITRE_MAX = 80


class AgentSessionNotFoundError(LookupError):
    """Aucune session de ce créateur sous cet identifiant."""


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
) -> AgentSession:
    session = AgentSession(
        creator_id=creator_id,
        title=title or "Nouvelle conversation",
        provider_id=provider_id,
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


async def supprimer(db: AsyncSession, creator_id: UUID, session_id: UUID) -> None:
    """Suppression logique : la trace reste, la session sort des listes."""
    session = await obtenir(db, creator_id, session_id)
    session.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
