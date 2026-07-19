from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.biblio_card import BiblioCard, CardStatus
from app.models.linked_account import LinkedAccount
from app.models.source import Source
from app.models.user import User
from app.schemas.linked_account import LinkedAccountOut, LinkedAccountsUpdate
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


async def _linked_accounts_for(db: AsyncSession, user_id) -> list[LinkedAccount]:
    result = await db.execute(
        select(LinkedAccount)
        .where(LinkedAccount.user_id == user_id)
        .order_by(LinkedAccount.created_at)
    )
    return list(result.scalars().all())


@router.get("/me/linked-accounts", response_model=list[LinkedAccountOut])
async def get_my_linked_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _linked_accounts_for(db, current_user.id)


@router.put("/me/linked-accounts", response_model=list[LinkedAccountOut])
async def replace_my_linked_accounts(
    payload: LinkedAccountsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remplace la liste complète (sémantique PUT — simple pour la v0)."""
    existing = await _linked_accounts_for(db, current_user.id)
    for acc in existing:
        await db.delete(acc)
    # Flush les DELETE avant les INSERT, sinon la contrainte unique peut
    # sauter si une même (platform, url) est re-soumise.
    await db.flush()
    seen: set[tuple[str, str]] = set()
    for item in payload.accounts:
        key = (item.platform.value, item.url)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            LinkedAccount(
                user_id=current_user.id,
                platform=item.platform.value,
                url=item.url,
                handle=item.handle,
            )
        )
    await db.commit()
    return await _linked_accounts_for(db, current_user.id)


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

    linked = await _linked_accounts_for(db, user.id)

    return {
        "slug": user.username,
        "display_name": user.display_name,
        "description": user.bio,
        "avatar_url": user.avatar_url,
        "public_key": user.public_key,
        "linked_accounts": [
            {
                "platform": a.platform,
                "url": a.url,
                "handle": a.handle,
                "verified": a.verified,
            }
            for a in linked
        ],
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
