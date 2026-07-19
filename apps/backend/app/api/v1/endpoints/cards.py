from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.claim_request import ClaimRequest
from app.models.user import User
from app.schemas.biblio_card import (
    CardCreate,
    CardDetail,
    CardResponse,
    CardUpdate,
    CreatorInfo,
)
from app.schemas.claim import ClaimRequestCreate, ClaimRequestResponse
from app.schemas.source import SourceResponse
from app.services.auth import AuthService
from app.services.card import CardService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cards"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_card_service(db: AsyncSession = Depends(get_db)) -> CardService:
    return CardService(db)


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


@router.get("/cards", response_model=list[CardResponse])
async def list_my_cards(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    from app.models.biblio_card import CardStatus

    status_enum = CardStatus(status_filter) if status_filter else None
    cards = await card_service.get_user_cards(current_user.id, status_enum, limit, offset)
    return cards


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def create_card(
    request: Request,
    card_data: CardCreate,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    existing = await card_service.get_card_by_slug(
        current_user.username, card_data.slug, published_only=False
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflict",
                "message": f"Card with slug '{card_data.slug}' already exists",
            },
        )
    card = await card_service.create_card(current_user.id, card_data)
    return card


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
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
    return card


@router.patch("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: UUID,
    card_data: CardUpdate,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
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

    from app.models.biblio_card import CardStatus

    if card.status == CardStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": "Cannot modify a published card"},
        )

    if card_data.title is not None:
        card.title = card_data.title
    if card_data.description is not None:
        card.description = card_data.description
    if card_data.content_url is not None:
        card.content_url = card_data.content_url
    if card_data.platform is not None:
        card.platform = card_data.platform.value

    # The card is already attached to the request session (via CardService);
    # opening a second session here raised InvalidRequestError. Commit in place.
    return await card_service.save_card(card)


@router.post("/cards/{card_id}/publish", response_model=dict)
async def publish_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_id(card_id)
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

    if not card.sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": "Cannot publish a card without sources"},
        )

    # Belt-and-suspenders: any exception raised during publish (MissingGreenlet,
    # asyncpg DataError, crypto error, etc.) must surface as a clean JSON 500
    # with CORS headers. Without this wrapper, an exception that aborts the
    # SQLAlchemy transaction leaves `get_db`'s post-yield `await session.commit()`
    # to raise a second time AFTER the response is being constructed, killing
    # the response stream so the browser receives no CORS header (visible as
    # "blocked by CORS policy" + ERR_FAILED, indistinguishable from a network
    # outage). See agent/PITFALLS.md §1.4 and §1.5.
    try:
        return await card_service.publish_card(card)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "publish_card failed: card_id=%s user_id=%s sources=%d type=%s",
            card_id,
            current_user.id,
            len(card.sources),
            type(exc).__name__,
        )
        # Rollback so `get_db`'s cleanup `commit()` doesn't trip on the aborted
        # transaction and corrupt the response stream.
        try:
            await card_service._db.rollback()
        except Exception:
            logger.exception("rollback after publish failure also failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "publish_failed",
                    "message": f"Publish failed: {type(exc).__name__}: {exc}",
                }
            },
        )


@router.post("/cards/{card_id}/restore", response_model=CardResponse)
async def restore_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.restore_card(card_id, current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found or not deleted"},
        )
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    card_service: CardService = Depends(get_card_service),
):
    deleted = await card_service.delete_card(card_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found or already published"},
        )


@router.get("/@{creator_slug}/{card_slug}", response_model=CardDetail)
async def get_public_card(
    creator_slug: str,
    card_slug: str,
    card_service: CardService = Depends(get_card_service),
):
    card = await card_service.get_card_by_slug(creator_slug, card_slug)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )

    stats = card_service.compute_stats(card)
    sources_response = [SourceResponse.model_validate(s) for s in card.sources]

    return CardDetail(
        id=card.id,
        slug=card.slug,
        title=card.title,
        description=card.description,
        content_url=card.content_url,
        platform=card.platform,
        content_type=card.content_type,
        status=card.status,
        is_seed=card.is_seed,
        published_at=card.published_at,
        created_at=card.created_at,
        updated_at=card.updated_at,
        creator=CreatorInfo(
            slug=card.user.username,
            display_name=card.user.display_name,
            bio=card.user.bio,
            avatar_url=card.user.avatar_url,
            public_key=card.user.public_key,
        ),
        sources=sources_response,
        stats=stats,
    )


@router.post(
    "/cards/{card_id}/claim-requests",
    response_model=ClaimRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")
async def create_claim_request(
    request: Request,
    card_id: UUID,
    payload: ClaimRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(BiblioCard, card_id)
    if card is None or card.deleted_at is not None or card.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if not card.is_seed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_claimable", "message": "This card is not a seed card"},
        )
    db.add(
        ClaimRequest(
            card_id=card.id,
            email=payload.email.lower().strip(),
            channel_url=payload.channel_url.strip(),
            message=payload.message,
        )
    )
    await db.commit()
    return ClaimRequestResponse()


# Card-level /verify endpoint removed (ADR-019 pivot to content attestations).
# Verification now lives at GET /attestations/{id}/verify. The frontend no
# longer calls /verify on cards — removing the dead endpoint avoids confusion.
