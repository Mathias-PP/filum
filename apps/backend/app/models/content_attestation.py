from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ContentAttestation(Base):
    __tablename__ = "content_attestations"
    __table_args__ = (Index("ix_content_attestations_user_url", "user_id", "content_url"),)

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
    content_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    attested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="content_attestations",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<ContentAttestation {self.id} user={self.user_id}>"
