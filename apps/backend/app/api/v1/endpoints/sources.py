from __future__ import annotations

import asyncio
from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.db.database import async_session_maker, get_db
from app.extractors import url_extractor
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.services.auth import AuthService
from app.services.wayback import WaybackService

router = APIRouter(prefix="/sources", tags=["sources"])
settings = get_settings()

# The event loop only keeps WEAK references to tasks: a fire-and-forget
# create_task() can be garbage-collected mid-flight, silently dropping the
# Wayback archive job (source stuck in "pending"). Hold a strong reference
# until the task completes.
_background_tasks: set[asyncio.Task] = set()


class ExtractResponse(BaseModel):
    title: str | None
    authors: str | None
    published_at: str | None
    description: str | None
    citations_count: int | None
    impact_factor: float | None


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get("/extract", response_model=ExtractResponse)
@limiter.limit("10/minute")
async def extract_url_metadata(
    request: Request,
    url: HttpUrl = Query(..., description="URL to extract metadata from"),
):
    """Extract title, authors, date, citations from a URL (best-effort, no auth required).

    Protected against SSRF: the URL is resolved and any non-public IP
    (loopback, private RFC1918, link-local, cloud-metadata 169.254.169.254,
    etc.) is rejected up-front. See `app.core.url_safety`.
    """
    try:
        # assert_url_is_safe does a blocking socket.getaddrinfo (DNS) — run it
        # in a worker thread so slow DNS doesn't stall the event loop.
        await asyncio.to_thread(assert_url_is_safe, str(url))
    except UnsafeUrlError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "unsafe_url", "message": str(e)},
        ) from e
    meta = await url_extractor.extract(str(url))
    return ExtractResponse(
        title=meta.title,
        authors=meta.authors,
        published_at=meta.published_at,
        description=meta.description,
        citations_count=meta.citations_count,
        impact_factor=meta.impact_factor,
    )


async def get_current_user(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    card_id: UUID = Query(..., description="Card ID to list sources for"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BiblioCard).where(BiblioCard.id == card_id, BiblioCard.deleted_at.is_(None))
    )
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

    source_result = await db.execute(
        select(Source)
        .options(selectinload(Source.excerpts))
        .where(Source.biblio_card_id == card_id, Source.deleted_at.is_(None))
        .order_by(Source.position)
    )
    return source_result.scalars().all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    card_id: UUID,
    source_data: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BiblioCard).where(BiblioCard.id == card_id, BiblioCard.deleted_at.is_(None))
    )
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

    # ADR-019 + ADR-020: published cards are mutable. The existing attestation
    # remains valid for its timestamped version; re-attestation policy is left
    # to a future ADR-021 if needed.

    max_position = await db.execute(
        select(func.max(Source.position)).where(Source.biblio_card_id == card_id)
    )
    max_pos = max_position.scalar() or 0

    # If the user provided a manual archive URL, we persist it directly and
    # mark the source as ARCHIVED, skipping the auto-archive background task.
    # Otherwise we start with PENDING and the background Wayback save runs.
    manual_archive = (source_data.archive_url or "").strip() or None

    source = Source(
        biblio_card_id=card_id,
        position=max_pos + 1,
        url=source_data.url,
        title=source_data.title,
        authors=source_data.authors,
        published_at=source_data.published_at,
        format=source_data.format.value,
        category=source_data.category.value,
        author_kind=source_data.author_kind.value,
        annotation=source_data.annotation,
        is_pivot=source_data.is_pivot,
        parent_source_id=source_data.parent_source_id,
        archive_url=manual_archive,
        archive_status="archived" if manual_archive else "pending",
        archive_timestamp=datetime.now().replace(tzinfo=None) if manual_archive else None,
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Eager-load excerpts to avoid MissingGreenlet during serialization
    result = await db.execute(
        select(Source).options(selectinload(Source.excerpts)).where(Source.id == source.id)
    )
    source = cast(Source, result.scalar_one())

    if not manual_archive:
        source_id_bg = source.id
        source_url_bg = source.url

        async def _archive_bg() -> None:
            async with async_session_maker() as bg_db:
                wayback = WaybackService(bg_db, settings.wayback_api_key)
                await wayback.archive_url(source_id_bg, source_url_bg)

        task = asyncio.create_task(_archive_bg())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    source_data: SourceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Source)
        .options(selectinload(Source.excerpts))
        .where(Source.id == source_id, Source.deleted_at.is_(None))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Source not found"},
        )

    result = await db.execute(
        select(BiblioCard).where(
            BiblioCard.id == source.biblio_card_id, BiblioCard.deleted_at.is_(None)
        )
    )
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

    # ADR-019 + ADR-020: published cards are mutable.

    update_data = source_data.model_dump(exclude_unset=True)
    # Special-case archive_url: when the user provides one explicitly we mark
    # the source ARCHIVED with the current timestamp. When they explicitly
    # clear it we revert to PENDING and let the next save (or a re-add) handle
    # auto-archiving.
    if "archive_url" in update_data:
        new_archive = (update_data["archive_url"] or "").strip() or None
        update_data["archive_url"] = new_archive
        if new_archive:
            update_data["archive_status"] = "archived"
            update_data["archive_timestamp"] = datetime.now().replace(tzinfo=None)
        else:
            update_data["archive_status"] = "pending"
            update_data["archive_timestamp"] = None

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
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Source not found"},
        )

    result = await db.execute(
        select(BiblioCard).where(
            BiblioCard.id == source.biblio_card_id, BiblioCard.deleted_at.is_(None)
        )
    )
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

    # ADR-019 + ADR-020: published cards are mutable.
    # Soft-delete: keep the row so historical references (parent_source_id
    # from other sources, citation graph snapshots, content_attestations)
    # remain intact. Queries on the public path filter `deleted_at IS NULL`.
    source.deleted_at = datetime.now().replace(tzinfo=None)
    await db.commit()
