from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.user import User
from app.services.auth import AuthService

router = APIRouter(prefix="/users", tags=["users"])


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

    cards_result = await db.execute(
        select(BiblioCard)
        .where(BiblioCard.user_id == user.id)
        .options(selectinload(BiblioCard.sources))
        .order_by(BiblioCard.published_at.desc())
    )
    cards = list(cards_result.scalars().all())

    total_sources = sum(len(c.sources) for c in cards)

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
                "total_sources": len(c.sources),
            }
            for c in cards
        ],
    }
