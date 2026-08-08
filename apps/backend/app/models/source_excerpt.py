from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    # Nullable et le reste : imposer un intitule ferait inventer une etiquette
    # la ou il n'y a rien a dire.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Selecteurs d'ancrage (cf. `app/services/excerpt_anchor.py`) : de quoi
    # retrouver le passage dans une page qui a bouge. Nullables et le restent —
    # les extraits saisis sans que le texte de la source soit connu n'en ont
    # pas, et un ancrage invente serait pire que pas d'ancrage.
    anchor_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Verdict de la derniere relecture. `None` veut dire « jamais relu » : un
    # etat a afficher tel quel, pas a combler par un defaut qui ferait passer
    # l'extrait pour verifie. `verified_text_source` distingue un verdict obtenu
    # contre la page publique d'un verdict obtenu contre un texte fourni.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verified_text_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source: Mapped[Source] = relationship("Source", back_populates="excerpts")

    def __repr__(self) -> str:
        snippet = self.text[:30] if self.text else ""
        return f"<SourceExcerpt {snippet}>"
