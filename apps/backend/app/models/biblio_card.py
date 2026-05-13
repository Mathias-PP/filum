from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.user import User


class CardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Platform(str, Enum):
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    BLOG = "blog"
    X = "x"
    BLUESKY = "bluesky"
    OTHER = "other"


class ContentType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    POST = "post"
    PODCAST = "podcast"
    OTHER = "other"


class BiblioCard(Base):
    __tablename__ = "biblio_cards"
    __table_args__ = (
        Index("ix_biblio_cards_user_status", "user_id", "status"),
        Index("ix_biblio_cards_canonical", "canonical_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Nullable: a draft card has no signature until publish_card() runs.
    # Migration 005 loosens the production Postgres constraints to match.
    canonical_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="biblio_cards",
        foreign_keys=[user_id],
    )
    sources: Mapped[list[Source]] = relationship(
        "Source",
        back_populates="biblio_card",
        cascade="all, delete-orphan",
        order_by="Source.position",
    )

    def __repr__(self) -> str:
        return f"<BiblioCard {self.slug}>"
