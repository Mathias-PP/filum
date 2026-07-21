from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.biblio_card import BiblioCard
    from app.models.source_excerpt import SourceExcerpt


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SourceFormat(str, Enum):
    TEXTE = "texte"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    DATA = "data"


class SourceCategory(str, Enum):
    ARTICLE_SCIENTIFIQUE = "article-scientifique"
    PREPRINT = "preprint"
    ARTICLE_PRESSE = "article-presse"
    COMMUNIQUE = "communique"
    DOCUMENTAIRE = "documentaire"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    BLOG = "blog"
    POST_SOCIAL = "post-social"
    LIVRE = "livre"
    PAGE_WEB = "page-web"
    NOTES = "notes"


class AuthorKind(str, Enum):
    CHERCHEUR = "chercheur"
    MEDIA = "media"
    INSTITUTION_PUBLIQUE = "institution-publique"
    GOUVERNEMENT = "gouvernement"
    ECOLE = "ecole"
    LABORATOIRE = "laboratoire"
    ENTREPRISE = "entreprise"
    ASSO = "asso"
    INDIVIDU = "individu"


class ArchiveStatus(str, Enum):
    PENDING = "pending"
    ARCHIVED = "archived"
    FAILED = "failed"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    biblio_card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("biblio_cards.id"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url: Mapped[str] = mapped_column(String(2000), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    author_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    annotation: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pivot: Mapped[bool] = mapped_column(default=False)
    archive_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    archive_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    archive_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parent_source_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=True,
        index=True,
    )
    # Fiche Philum publique referencee par cette source (resolue a la creation
    # quand l'URL matche /@{username}/{slug} sur notre propre frontend).
    linked_card_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("biblio_cards.id"),
        nullable=True,
        index=True,
    )
    conflict_of_interest: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscribers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impact_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Soft-delete: a non-null value hides the row from all standard queries.
    # See migration 008_source_deleted_at + the matching .deleted_at columns
    # already present on User (TimestampMixin) and BiblioCard.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    biblio_card: Mapped[BiblioCard] = relationship(
        "BiblioCard",
        back_populates="sources",
        foreign_keys=[biblio_card_id],
    )
    linked_card: Mapped[BiblioCard | None] = relationship(
        "BiblioCard",
        foreign_keys=[linked_card_id],
    )
    parent: Mapped[Source | None] = relationship(
        "Source",
        remote_side="Source.id",
        foreign_keys=[parent_source_id],
    )
    excerpts: Mapped[list[SourceExcerpt]] = relationship(
        "SourceExcerpt",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="SourceExcerpt.position",
    )

    def __repr__(self) -> str:
        return f"<Source {self.title or self.url[:30]}>"
