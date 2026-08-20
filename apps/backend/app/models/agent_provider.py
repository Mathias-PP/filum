from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AgentProvider(Base):
    """Un compte IA enregistré par un créateur (BYOK).

    La clé API n'est jamais stockée ni renvoyée en clair : seule
    ``api_key_enc`` (AES-GCM via le ``master_encryption_key``) existe en base,
    et le déchiffrement ne se fait que dans le service dédié.
    """

    __tablename__ = "agent_providers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=None,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(default=None, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "provider",
            "base_url",
            "model",
            name="uq_agent_providers_creator_provider_url_model",
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentProvider {self.provider} {self.model} creator={self.creator_id}>"
