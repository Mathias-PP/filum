"""Endpoints des providers IA BYOK d'un créateur.

CRUD masqué (jamais la clé en clair), désignation du défaut, test de clé, et
notice de souveraineté factuelle pour tous les providers.
"""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_provider import (
    AgentProviderCreate,
    AgentProviderRead,
    AgentProviderTestResult,
    AgentProviderUpdate,
)
from app.services.agent_providers import (
    DATA_SCOPE_NOTICE,
    PROVIDER_META,
    AgentProviderError,
    AgentProviderNotFoundError,
    creer,
    lister,
    mettre_a_jour,
    supprimer,
    tester,
)

settings = get_settings()

router = APIRouter(prefix="/agent/providers", tags=["agent-providers"])


def get_http_client() -> httpx.AsyncBaseTransport | None:
    """Transport httpx injectable (``MockTransport`` dans les tests). Réseau par défaut."""
    return None


@router.get("/meta")
async def provider_meta():
    """Notice de souveraineté, factuelle et sans discrimination.

    L'utilisateur décide, Philum informe : pays d'hébergement connu et périmètre
    précis des données qui transitent pendant un échange.
    """
    return {"data_scope": DATA_SCOPE_NOTICE, "providers": PROVIDER_META}


@router.get("", response_model=list[AgentProviderRead])
async def lister_mes_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lister(db, current_user.id)


@router.post("", response_model=AgentProviderRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def creer_provider(
    request: Request,
    body: AgentProviderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await creer(db, current_user.id, body)
    except AgentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_provider", "message": str(exc)},
        ) from exc


@router.patch("/{provider_id}", response_model=AgentProviderRead)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def mettre_a_jour_provider(
    provider_id: UUID,
    request: Request,
    body: AgentProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await mettre_a_jour(db, current_user.id, provider_id, body)
    except AgentProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc
    except AgentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_provider", "message": str(exc)},
        ) from exc


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def supprimer_provider(
    provider_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await supprimer(db, current_user.id, provider_id)
    except AgentProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc


@router.post("/{provider_id}/test", response_model=AgentProviderTestResult)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def tester_provider(
    provider_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    transport: httpx.AsyncBaseTransport | None = Depends(get_http_client),
):
    try:
        return await tester(db, current_user.id, provider_id, transport=transport)
    except AgentProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc
