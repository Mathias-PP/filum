from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin


class LinkedAccount(Base, TimestampMixin):
    """Compte plateforme lié au profil créateur (v0 déclaratif, cf. .docs/18)."""

    __tablename__ = "linked_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", "url"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # v1+ : renseignés par la vérification (backlink, bio-code, oauth)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    @property
    def verified(self) -> bool:
        return self.verified_at is not None

    def __repr__(self) -> str:
        return f"<LinkedAccount {self.platform}:{self.handle or self.url}>"
