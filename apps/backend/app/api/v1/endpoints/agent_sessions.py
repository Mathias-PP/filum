"""Sessions de chat de l'agent, et réponse humaine aux actions sensibles.

Les sessions donnent une mémoire à l'agent : sans elles, un rechargement de
page efface la conversation et le modèle repart de zéro. ``POST /agent/approve``
est l'autre moitié du flux SSE : la boucle s'est arrêtée sur un
``approval_request``, ce endpoint la relance.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_chat import (
    AgentApprovalDecision,
    AgentMessageRead,
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
    AgentSessionUsage,
)
from app.services import agent_approvals, agent_sessions

settings = get_settings()

router = APIRouter(prefix="/agent", tags=["agent-sessions"])


@router.get("/sessions", response_model=list[AgentSessionRead])
async def lister_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_sessions.lister(db, current_user.id)


@router.post("/sessions", response_model=AgentSessionRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def creer_session(
    request: Request,
    body: AgentSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_sessions.creer(
        db, current_user.id, title=body.title, provider_id=body.provider_id
    )


@router.get("/sessions/{session_id}", response_model=AgentSessionRead)
async def lire_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await agent_sessions.obtenir(db, current_user.id, session_id)
    except agent_sessions.AgentSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": str(exc)},
        ) from exc


@router.patch("/sessions/{session_id}", response_model=AgentSessionRead)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def mettre_a_jour_session(
    session_id: UUID,
    request: Request,
    body: AgentSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Renomme la conversation et/ou change sa cle provider ou son modele."""
    try:
        return await agent_sessions.mettre_a_jour(
            db,
            current_user.id,
            session_id,
            title=body.title,
            provider_id=body.provider_id,
            model_override=body.model_override,
        )
    except agent_sessions.AgentSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": str(exc)},
        ) from exc


@router.get("/sessions/{session_id}/messages", response_model=list[AgentMessageRead])
async def lister_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await agent_sessions.messages(db, current_user.id, session_id)
    except agent_sessions.AgentSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": str(exc)},
        ) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await agent_sessions.supprimer(db, current_user.id, session_id)
    except agent_sessions.AgentSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": str(exc)},
        ) from exc


@router.get("/sessions/{session_id}/usage", response_model=AgentSessionUsage)
async def usage_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await agent_sessions.usage_session(db, current_user.id, session_id)
    except agent_sessions.AgentSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": str(exc)},
        ) from exc
    return AgentSessionUsage(**data)


@router.post("/approve", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def repondre_approbation(
    request: Request,
    body: AgentApprovalDecision,
    current_user: User = Depends(get_current_user),
):
    """Débloque la boucle suspendue sur ``request_id``, pour ce créateur seul."""
    try:
        agent_approvals.resoudre(body.request_id, current_user.id, body.approved)
    except agent_approvals.ApprovalInconnueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "approval_not_found", "message": str(exc)},
        ) from exc
