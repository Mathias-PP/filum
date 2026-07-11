from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import Source
from app.models.user import User
from app.services.auth import AuthService

router = APIRouter(prefix="/users", tags=["users"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


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


@router.get("/@{slug}", response_model=dict)
async def get_user_profile(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == slug))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "User not found"},
        )

    # Public profile: only PUBLISHED cards (drafts were leaking here), and
    # count sources in SQL instead of eager-loading every Source row.
    cards_result = await db.execute(
        select(BiblioCard, func.count(Source.id).label("source_count"))
        .outerjoin(
            Source,
            (Source.biblio_card_id == BiblioCard.id) & Source.deleted_at.is_(None),
        )
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.deleted_at.is_(None),
            BiblioCard.status == CardStatus.PUBLISHED,
        )
        .group_by(BiblioCard.id)
        .order_by(BiblioCard.published_at.desc())
    )
    rows = cards_result.all()
    cards = [row[0] for row in rows]
    source_counts = {row[0].id: row[1] for row in rows}

    total_sources = sum(source_counts.values())

    return {
        "slug": user.username,
        "display_name": user.display_name,
        "description": user.bio,
        "avatar_url": user.avatar_url,
        "public_key": user.public_key,
        "stats": {
            "total_cards": len(cards),
            "total_sources": total_sources,
            "first_published_at": cards[-1].published_at.isoformat()
            if cards and cards[-1].published_at
            else None,
            "last_published_at": cards[0].published_at.isoformat()
            if cards and cards[0].published_at
            else None,
        },
        "cards": [
            {
                "slug": c.slug,
                "title": c.title,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                "total_sources": source_counts[c.id],
            }
            for c in cards
        ],
    }
