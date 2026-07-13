"""Fonctions read-only du serveur MCP.

Fonctions pures (session en parametre) pour rester testables sans le
protocole MCP. Reponses volontairement compactes : l'IA cliente ne charge
que les noeuds qu'elle visite (frugalite en tokens).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User

_PUBLISHED = (BiblioCard.status == "published") & BiblioCard.deleted_at.is_(None)


async def search_cards(db: AsyncSession, query: str, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            _PUBLISHED,
            func.lower(BiblioCard.title).contains(query.lower())
            | func.lower(User.username).contains(query.lower()),
        )
        .options(selectinload(BiblioCard.user))
        .order_by(BiblioCard.published_at.desc())
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]


async def get_card(db: AsyncSession, creator: str, slug: str) -> dict[str, Any] | None:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLISHED, User.username == creator, BiblioCard.slug == slug)
        .options(selectinload(BiblioCard.user), selectinload(BiblioCard.sources))
    )
    card = await db.scalar(stmt)
    if card is None:
        return None
    return {
        "creator": card.user.username,
        "slug": card.slug,
        "title": card.title,
        "description": card.description,
        "content_url": card.content_url,
        "published_at": card.published_at.isoformat() if card.published_at else None,
        "sources": [
            {
                "id": str(s.id),
                "title": s.title,
                "url": s.url,
                "category": s.category,
                "author_kind": s.author_kind,
            }
            for s in card.sources
            if s.deleted_at is None
        ],
    }


async def get_source(db: AsyncSession, source_id: str) -> dict[str, Any] | None:
    try:
        sid = UUID(source_id)
    except ValueError:
        return None
    source = await db.scalar(
        select(Source).where(Source.id == sid, Source.deleted_at.is_(None))
    )
    if source is None:
        return None
    return {
        "id": str(source.id),
        "title": source.title,
        "url": source.url,
        "authors": source.authors,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "format": source.format,
        "category": source.category,
        "author_kind": source.author_kind,
        "annotation": source.annotation,
        "archive_url": source.archive_url,
        "archive_timestamp": (
            source.archive_timestamp.isoformat() if source.archive_timestamp else None
        ),
    }


async def find_cards_citing(db: AsyncSession, url: str, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(BiblioCard)
        .join(Source, Source.biblio_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLISHED, Source.deleted_at.is_(None), Source.url == url.strip())
        .options(selectinload(BiblioCard.user))
        .distinct()
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]
