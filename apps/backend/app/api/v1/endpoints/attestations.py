from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.db.database import get_db
from app.models.user import User
from app.schemas.attestation import (
    AttestationCreate,
    AttestationResponse,
    AttestationVerifyResponse,
)
from app.services.attestation import AttestationService
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attestations"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_attestation_service(db: AsyncSession = Depends(get_db)) -> AttestationService:
    return AttestationService(db)


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.post(
    "/attestations/content",
    response_model=AttestationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attestation(
    body: AttestationCreate,
    current_user: User = Depends(get_current_user),
    attestation_service: AttestationService = Depends(get_attestation_service),
):
    attestation = await attestation_service.create_attestation(current_user, body.content_url)
    return AttestationResponse(
        id=attestation.id,
        user_id=attestation.user_id,
        content_url=attestation.content_url,
        attested_at=attestation.attested_at,
        canonical_hash=attestation.canonical_hash,
        signature=attestation.signature,
        created_at=attestation.created_at,
    )


@router.get("/attestations/{attestation_id}", response_model=AttestationResponse)
async def get_attestation(
    attestation_id: UUID,
    attestation_service: AttestationService = Depends(get_attestation_service),
):
    attestation = await attestation_service.get_attestation(attestation_id)
    if not attestation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Attestation not found"},
        )
    return AttestationResponse(
        id=attestation.id,
        user_id=attestation.user_id,
        content_url=attestation.content_url,
        attested_at=attestation.attested_at,
        canonical_hash=attestation.canonical_hash,
        signature=attestation.signature,
        created_at=attestation.created_at,
    )


@router.get("/attestations/{attestation_id}/verify", response_model=AttestationVerifyResponse)
async def verify_attestation(
    attestation_id: UUID,
    attestation_service: AttestationService = Depends(get_attestation_service),
):
    attestation = await attestation_service.get_attestation(attestation_id)
    if not attestation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Attestation not found"},
        )
    result = await attestation_service.verify_attestation(attestation)
    return AttestationVerifyResponse(
        valid=result["valid"],
        attestation_id=attestation_id,
        content_url=attestation.content_url,
        creator_slug=result.get("creator_slug"),
        public_key=result.get("public_key"),
        reason=result.get("reason"),
    )
