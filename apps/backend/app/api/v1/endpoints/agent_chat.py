"""Endpoint chat de l'agent BYOK : un message, un flux SSE.

Le client envoie ``{message, history?, session_id?}`` ; le serveur rend un flux
d'événements (``text/event-stream``) produits par la boucle de l'agent :

- ``session`` : l'identifiant de la session, émis en tête (créée si absente) ;
- ``message_delta`` : un bout de la réponse finale du modèle ;
- ``tool_call`` / ``tool_result`` : un outil exécuté et son résultat ;
- ``approval_request`` / ``approval_resolved`` : une action sensible soumise
  à validation humaine, puis sa résolution ;
- ``done`` (motif ``complete``) : fin normale ;
- ``error`` : erreur provider ou borne atteinte.

Avec une session, l'historique vient de la base et le tour y est écrit en
append-only. L'approbation suspend réellement la boucle : elle attend
``POST /agent/approve`` et refuse au bout de ``agent_approvals.DELAI_MAX``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.agent_providers import get_http_client
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_chat import AgentChatRequest
from app.services import agent_approvals, agent_sessions
from app.services.agent import boucle
from app.services.agent_providers import resoudre_defaut

settings = get_settings()

router = APIRouter(prefix="/agent", tags=["agent-chat"])


def get_approver():
    """Fabrique le callback d'approbation. Surchargeable en test.

    Rend une fonction qui, pour un ``creator_id``, suspend la boucle jusqu'à
    la réponse humaine via ``POST /agent/approve``.
    """

    def pour(creator_id):
        async def approuver(request_id: str, tool: str, args: dict[str, Any]) -> bool:
            return await agent_approvals.attendre(request_id, creator_id)

        return approuver

    return pour


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat_agent(
    request: Request,
    body: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    transport: httpx.AsyncBaseTransport | None = Depends(get_http_client),
    fabrique_approbation=Depends(get_approver),
):
    if body.session_id is None:
        session = await agent_sessions.creer(
            db,
            current_user.id,
            title=agent_sessions.titre_depuis_message(body.message),
        )
        messages: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in body.history
        ]
    else:
        try:
            session = await agent_sessions.obtenir(db, current_user.id, body.session_id)
        except agent_sessions.AgentSessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "session_not_found", "message": str(exc)},
            ) from exc
        # L'historique persisté fait autorité : ce que le client renvoie
        # pourrait avoir été retouché en route.
        messages = await agent_sessions.historique_pour_modele(db, current_user.id, session.id)

    provider = await resoudre_defaut(db, current_user.id)
    if provider is None:
        erreur = {
            "type": "error",
            "payload": {
                "message": "Aucun provider IA par défaut configuré. Définis-en un dans Agent → Providers."
            },
        }
        return StreamingResponse(
            iter([_sse({"type": "session", "payload": {"id": str(session.id)}}), _sse(erreur)]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    messages.append({"role": "user", "content": body.message})
    await agent_sessions.ajouter_message(db, session, role="user", content=body.message)
    # `boucle` insère le prompt système en tête : le tour commence donc un cran
    # plus loin que la longueur d'avant l'appel.
    depart = len(messages) + 1
    approuver = fabrique_approbation(current_user.id)

    async def gen():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        reponse_finale: list[str] = []

        async def emit(event: dict[str, Any]) -> None:
            if event.get("type") == "message_delta":
                reponse_finale.append(event["payload"]["delta"])
            await queue.put(event)

        async def runner() -> None:
            try:
                await boucle(
                    db,
                    current_user,
                    provider,
                    messages,
                    emit,
                    approuver,
                    transport=transport,
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())
        yield _sse({"type": "session", "payload": {"id": str(session.id)}})
        # Sans ce `finally`, un client qui ferme l'onglet laisse la boucle
        # tourner jusqu'a 24 tours : elle continue de facturer le provider et
        # d'ecrire via une session de base que FastAPI a deja fermee.
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse(event)
            await task
            await _persister_tour(db, session, messages[depart:], "".join(reponse_finale))
        finally:
            task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _persister_tour(
    db: AsyncSession,
    session,
    ajouts: list[dict[str, Any]],
    reponse_finale: str,
) -> None:
    """Écrit le tour en base, append-only, dans l'ordre où il s'est produit.

    La réponse textuelle finale n'est pas dans ``messages`` : la boucle
    l'émet en ``message_delta`` sans la rajouter à l'historique. On la
    recompose ici pour que le tour suivant la voie.
    """
    for message in ajouts:
        if message.get("role") == "tool":
            await agent_sessions.ajouter_message(
                db,
                session,
                role="tool",
                content=message.get("content") or "",
                tool_name=message.get("name"),
                tool_call_id=message.get("tool_call_id"),
            )
        else:
            await agent_sessions.ajouter_message(
                db,
                session,
                role=message.get("role") or "assistant",
                content=message.get("content") or "",
                tool_calls=message.get("tool_calls"),
            )
    if reponse_finale:
        await agent_sessions.ajouter_message(db, session, role="assistant", content=reponse_finale)
