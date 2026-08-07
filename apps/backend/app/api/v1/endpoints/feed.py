"""Feed chronologique public — un registre, pas un fil algorithmique.

Voir `.docs/20-profils-et-feed.md`. Une entree = une publication effective
d'une fiche publique. Ordre strictement anti-chronologique, jamais autre.
Publiquement lisible, anonyme, meme forme pour un humain qu'un agent.

Aucun compteur d'engagement dans la reponse : ce serait ouvrir le concours
de popularite que le format refuse d'instituer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.feed_event import FeedEvent
from app.models.user import User

router = APIRouter(prefix="/feed", tags=["feed"])


class FeedEntry(BaseModel):
    id: str
    kind: str
    occurred_at: datetime
    unpublished_at: datetime | None
    creator_slug: str
    creator_display_name: str | None
    card_title: str
    card_url: str
    card_description: str | None


class FeedResponse(BaseModel):
    limit: int
    before: datetime | None
    next_before: datetime | None
    entries: list[FeedEntry]


def _base() -> Select[Any]:
    # On ne trie et ne renvoie que les evenements dont la fiche est encore
    # visible et publique — une fiche depubliee ou passee en prive doit
    # disparaitre du feed (question ouverte Q-feed-1 tranchee ici en faveur
    # du retrait plutot que du marquage « depubliee »).
    return (
        select(FeedEvent, BiblioCard, User.username, User.display_name)
        .join(BiblioCard, BiblioCard.id == FeedEvent.card_id)
        .join(User, User.id == FeedEvent.actor_id)
        .where(
            and_(
                BiblioCard.deleted_at.is_(None),
                BiblioCard.status == "published",
                BiblioCard.visibility == "public",
                FeedEvent.unpublished_at.is_(None),
            )
        )
    )


@router.get("", response_model=FeedResponse)
async def read_feed(
    limit: int = Query(20, ge=1, le=100),
    before: datetime | None = Query(
        None,
        description="Curseur : ne renvoyer que les entrees strictement anterieures. "
        "Cursor-based, jamais offset : un feed grandit constamment et l'offset "
        "sauterait des entrees quand une nouvelle apparait entre deux appels.",
    ),
    db: AsyncSession = Depends(get_db),
) -> FeedResponse:
    stmt = _base()
    if before is not None:
        stmt = stmt.where(FeedEvent.occurred_at < before)
    stmt = stmt.order_by(FeedEvent.occurred_at.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).all()

    # +1 pour savoir s'il reste une page sans faire un COUNT global (couteux
    # sur une table qui grandit sans bornes).
    has_more = len(rows) > limit
    kept = rows[:limit]

    base_url = get_settings().frontend_base_url.rstrip("/")
    entries = [
        FeedEntry(
            id=str(event.id),
            kind=event.kind,
            occurred_at=event.occurred_at,
            unpublished_at=event.unpublished_at,
            creator_slug=username,
            creator_display_name=display_name,
            card_title=card.title,
            card_url=f"{base_url}/@{username}/{card.slug}",
            card_description=card.description,
        )
        for event, card, username, display_name in kept
    ]

    return FeedResponse(
        limit=limit,
        before=before,
        next_before=(kept[-1][0].occurred_at if has_more and kept else None),
        entries=entries,
    )
