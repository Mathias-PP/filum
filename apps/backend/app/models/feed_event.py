from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# Voir `.docs/20-profils-et-feed.md` — cette table est un registre chronologique,
# jamais un fil algorithmique. `kind` reste ouvert pour accueillir des types
# futurs (`card_updated`, `claim_verified`) sans migration structurelle.


class FeedEventKind:
    CARD_PUBLISHED = "card_published"


class FeedEvent(Base):
    __tablename__ = "feed_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("biblio_cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # Non NULL si la fiche a ete depubliee apres coup. L'entree reste, on ne
    # peut pas effacer le passe — meme logique que l'attestation de contenu.
    unpublished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
