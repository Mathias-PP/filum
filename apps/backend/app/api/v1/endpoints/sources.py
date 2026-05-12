from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db
from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import Source
from app.models.user import User
from app.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.services.auth import AuthService
from app.services.wayback import WaybackService

router = APIRouter(prefix="/sources", tags=["sources"])
settings = get_settings()


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(request, auth_service: AuthService = Depends(get_auth_service)) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    card_id: UUID,
    source_data: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BiblioCard).where(BiblioCard.id == card_id))
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    if card.status == CardStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Cannot add sources to a published card",
            },
        )

    max_position = await db.execute(
        select(func.max(Source.position)).where(Source.biblio_card_id == card_id)
    )
    max_pos = max_position.scalar() or 0

    source = Source(
        biblio_card_id=card_id,
        position=max_pos + 1,
        url=source_data.url,
        title=source_data.title,
        authors=source_data.authors,
        published_at=source_data.published_at,
        source_type=source_data.source_type.value,
        authority_level=source_data.authority_level.value,
        annotation=source_data.annotation,
        is_pivot=source_data.is_pivot,
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    wayback = WaybackService(db, settings.wayback_api_key)
    await wayback.archive_url(source.id, source.url)

    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    source_data: SourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Source not found"},
        )

    result = await db.execute(select(BiblioCard).where(BiblioCard.id == source.biblio_card_id))
    card = cast(BiblioCard | None, result.scalar_one_or_none())

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )

    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    if card.status == CardStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Cannot modify sources of a published card",
            },
        )

    update_data = source_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)

    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Source not found"},
        )

    result = await db.execute(select(BiblioCard).where(BiblioCard.id == source.biblio_card_id))
    card = cast(BiblioCard | None, result.scalar_one_or_none())

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )

    if card.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )

    if card.status == CardStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": "Cannot delete sources from a published card",
            },
        )

    await db.delete(source)
    await db.commit()
