"""Endpoint chat de l'agent BYOK : un message, un flux SSE.

Le client envoie ``{message, history}`` ; le serveur rend un flux
d'événements (``text/event-stream``) produits par la boucle de l'agent :

- ``message_delta`` : un bout de la réponse finale du modèle ;
- ``tool_call`` / ``tool_result`` : un outil exécuté et son résultat ;
- ``approval_request`` / ``approval_resolved`` : une action sensible soumise
  à validation humaine, puis sa résolution ;
- ``done`` (motif ``complete``) : fin normale ;
- ``error`` : erreur provider ou borne atteinte.

Phase 3 : l'approbation est un **refus par défaut** (``get_approver``) —
aucune action sensible n'est exécutée tant que la session/reprise de la
Phase 4 n'existe pas. Les tests surchargent ce callback.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.agent_providers import get_http_client
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_chat import AgentChatRequest
from app.services.agent import boucle
from app.services.agent_providers import resoudre_defaut

settings = get_settings()

router = APIRouter(prefix="/agent", tags=["agent-chat"])


async def _refus_par_defaut(tool: str, args: dict[str, Any]) -> bool:
    """Phase 3 : sans session, aucune action sensible n'est exécutée.

    La boucle émet quand même ``approval_request`` puis ``approval_resolved``
    (false) : le client sait que l'action a été suspendue et refusée. La
    Phase 4 remplace ce refus par une approbation humaine réelle.
    """
    return False


def get_approver():
    """Callback d'approbation injectable (tests : feu vert automatique)."""
    return _refus_par_defaut


@router.post("/chat")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat_agent(
    request: Request,
    body: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    transport: httpx.AsyncBaseTransport | None = Depends(get_http_client),
    approuver=Depends(get_approver),
):
    provider = await resoudre_defaut(db, current_user.id)
    if provider is None:
        message = {
            "type": "error",
            "payload": {
                "message": "Aucun provider IA par défaut configuré. Définis-en un dans Agent → Providers."
            },
        }
        return StreamingResponse(
            iter([f"data: {json.dumps(message, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    messages = [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    async def gen():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def emit(event: dict[str, Any]) -> None:
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
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        await task

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
