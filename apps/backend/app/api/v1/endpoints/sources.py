from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
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
from app.services.card_link import resolve_linked_card_id
from app.services.wayback import WaybackService

logger = logging.getLogger(__name__)

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
    # Suggestions de taxonomie ADR-020 (Crossref ou LLM, null si indéterminé).
    format: str | None = None
    category: str | None = None
    author_kind: str | None = None


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
        format=meta.format,
        category=meta.category,
        author_kind=meta.author_kind,
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

    linked_card_id = await resolve_linked_card_id(db, source_data.url, exclude_card_id=card_id)

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
        linked_card_id=linked_card_id,
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


# --- Batch creation -------------------------------------------------------
#
# Le flow /dashboard/from-url cree jusqu'a 150+ sources en un clic. Le
# faire via 150 POST HTTP separes en JS :
#   - est lent (150 x latence + Wayback en background = ~30-60s)
#   - fragile (un fetch qui timeout coupe la boucle sans indice clair)
#   - genere 150 lignes de log CI/prod pour un seul evenement produit
# L'endpoint batch reunit tout dans une seule transaction + declenche les
# archives Wayback en parallele apres commit. Retourne created + failed
# separement pour que le frontend affiche precisement ce qui a rate.

_BATCH_MAX = 200


class SourceBatchRequest(BaseModel):
    sources: list[SourceCreate] = Field(min_length=1, max_length=_BATCH_MAX)


class SourceBatchError(BaseModel):
    index: int
    url: str
    error: str


class SourceBatchResponse(BaseModel):
    created: list[SourceResponse]
    failed: list[SourceBatchError]


@router.post("/batch", response_model=SourceBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_sources_batch(
    request: Request,
    body: SourceBatchRequest,
    card_id: UUID = Query(..., description="Card ID to attach the sources to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cree N sources en une transaction. Ce qui echoue est retourne dans
    ``failed`` avec la raison, ce qui reussit dans ``created``.

    Impact archives Wayback : chaque source non-manuellement-archivee
    declenche une tache de fond apres commit (idem POST individuel).
    """
    # Ownership check
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

    max_position_row = await db.execute(
        select(func.max(Source.position)).where(Source.biblio_card_id == card_id)
    )
    next_pos = (max_position_row.scalar() or 0) + 1

    created: list[Source] = []
    failed: list[SourceBatchError] = []

    for i, sd in enumerate(body.sources):
        try:
            manual_archive = (sd.archive_url or "").strip() or None
            linked_card_id = await resolve_linked_card_id(db, sd.url, exclude_card_id=card_id)
            source = Source(
                biblio_card_id=card_id,
                position=next_pos,
                url=sd.url,
                title=sd.title,
                authors=sd.authors,
                published_at=sd.published_at,
                format=sd.format.value,
                category=sd.category.value,
                author_kind=sd.author_kind.value,
                annotation=sd.annotation,
                is_pivot=sd.is_pivot,
                parent_source_id=sd.parent_source_id,
                linked_card_id=linked_card_id,
                archive_url=manual_archive,
                archive_status="archived" if manual_archive else "pending",
                archive_timestamp=datetime.now().replace(tzinfo=None) if manual_archive else None,
            )
            db.add(source)
            await db.flush()  # attribue l'ID sans commit
            created.append(source)
            next_pos += 1
        except Exception as exc:
            logger.warning(
                "batch source create failed idx=%s url=%s error=%s: %s",
                i,
                sd.url,
                type(exc).__name__,
                exc,
            )
            failed.append(SourceBatchError(index=i, url=sd.url, error=str(exc)))
            # continue : les autres sources doivent quand meme passer.
            # SQLAlchemy garde la session sane si le flush n'a pas ajoute
            # d'objet corrompu.

    await db.commit()

    # Recharge les sources avec excerpts eager-loaded pour serialisation.
    created_ids = [s.id for s in created]
    if created_ids:
        refresh = await db.execute(
            select(Source).options(selectinload(Source.excerpts)).where(Source.id.in_(created_ids))
        )
        created_full = list(refresh.scalars().all())
    else:
        created_full = []

    # Declenche les archives Wayback en parallele (fire-and-forget).
    for src in created_full:
        if src.archive_status == "pending":
            src_id = src.id
            src_url = src.url

            async def _archive_bg(sid=src_id, surl=src_url) -> None:
                async with async_session_maker() as bg_db:
                    wayback = WaybackService(bg_db, settings.wayback_api_key)
                    await wayback.archive_url(sid, surl)

            task = asyncio.create_task(_archive_bg())
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

    return SourceBatchResponse(
        created=[SourceResponse.model_validate(s) for s in created_full],
        failed=failed,
    )


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
