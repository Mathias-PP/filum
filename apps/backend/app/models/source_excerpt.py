from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.source import Source


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SourceExcerpt(Base):
    __tablename__ = "source_excerpts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source: Mapped[Source] = relationship("Source", back_populates="excerpts")

    def __repr__(self) -> str:
        snippet = self.text[:30] if self.text else ""
        return f"<SourceExcerpt {snippet}>"
