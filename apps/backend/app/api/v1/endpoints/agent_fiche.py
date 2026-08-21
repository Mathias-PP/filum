"""Endpoints du run de fiche : lancer les étages, suivre l'avancement.

``POST /agent/fiche`` rend le même genre de flux SSE que le chat, avec trois
événements en plus : ``stage_start``, ``stage_done`` et ``stage_failed``, et
un champ ``stage`` sur chaque événement de la boucle. Le run porte une
session, donc le compte rendu de chaque étage se relit ensuite dans
l'historique comme n'importe quelle conversation.

Le lancement est un endpoint plutôt qu'un outil : sept boucles enchaînées
coûtent cher, l'utilisateur doit voir ce qu'il déclenche.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.agent_chat import get_approver
from app.api.v1.endpoints.agent_providers import get_http_client
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_chat import AgentFicheRequest
from app.services import agent_fiche, agent_sessions
from app.services.agent_providers import resoudre_defaut

settings = get_settings()

router = APIRouter(prefix="/agent/fiche", tags=["agent-fiche"])


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/{slug}")
async def etat_fiche(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Où en est le run : quels étages ont déposé leur compte rendu."""
    return await agent_fiche.etat(db, current_user.id, slug)


@router.post("")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def lancer_fiche(
    request: Request,
    body: AgentFicheRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    transport: httpx.AsyncBaseTransport | None = Depends(get_http_client),
    fabrique_approbation=Depends(get_approver),
):
    provider = await resoudre_defaut(db, current_user.id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_default_provider",
                "message": "Aucun provider IA par défaut configuré.",
            },
        )

    session = await agent_sessions.creer(db, current_user.id, title=f"Fiche : {body.slug}")
    await agent_sessions.ajouter_message(
        db,
        session,
        role="user",
        content=f"Créer la fiche « {body.slug} » à partir de {body.content_url}.",
    )
    approuver = fabrique_approbation(current_user.id)

    async def gen():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def emit(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def runner() -> None:
            try:
                await agent_fiche.lancer(
                    db,
                    current_user,
                    provider,
                    slug=body.slug,
                    content_url=body.content_url,
                    emit=emit,
                    approuver=approuver,
                    transport=transport,
                    depuis=body.depuis,
                )
            except agent_fiche.FicheError as exc:
                await queue.put({"type": "error", "payload": {"message": str(exc)}})
            finally:
                await queue.put(None)

        franchis: list[dict[str, Any]] = []
        task = asyncio.create_task(runner())
        yield _sse({"type": "session", "payload": {"id": str(session.id)}})
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                if event.get("type") == "stage_done":
                    franchis.append(event["payload"])
                yield _sse(event)
            await task
            # Écrit après le run, jamais pendant : la session de base est déjà
            # occupée par l'orchestrateur, et deux opérations concurrentes
            # dessus font sauter SQLAlchemy.
            await _tracer_etages(db, session, franchis)
        finally:
            task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _tracer_etages(db: AsyncSession, session, franchis: list[dict[str, Any]]) -> None:
    """Note les étages franchis dans le journal de la session, append-only."""
    for payload in franchis:
        await agent_sessions.ajouter_message(
            db,
            session,
            role="assistant",
            content=f"Étage {payload.get('stage')} terminé, compte rendu dans "
            f"{payload.get('output')}",
        )
    if franchis:
        await db.commit()
