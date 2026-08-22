from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

#: JSONB en PostgreSQL (indexable, typé), JSON portable ailleurs (SQLite des tests).
_JSON_LIST = JSON().with_variant(JSONB(), "postgresql")


class AgentSession(Base):
    """Une conversation entre un créateur et son agent BYOK."""

    __tablename__ = "agent_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    provider_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_override: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Slug de l'agent nommé de cette session (fichier `agents/<slug>.yaml` du
    #: workspace). NULL = assistant généraliste, tous outils, tout `shared/`.
    agent_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentSession {self.id} creator={self.creator_id}>"


class AgentMessage(Base):
    """Un message d'une session. Append-only : jamais d'UPDATE.

    Réécrire un message ferait mentir la trace sur ce que le modèle avait
    sous les yeux au moment où il a choisi un outil.
    """

    __tablename__ = "agent_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(_JSON_LIST, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Identifiant du tool_call auquel ce message ``tool`` répond. La spec OpenAI
    # l'exige sur les messages de rôle ``tool`` ; Gemini rejette HTTP 400
    # INVALID_ARGUMENT sans lui. Nullable pour les rôles non-tool et pour la
    # rétrocompat des lignes anciennes (leur session ne pourra pas etre reprise
    # sur Gemini mais aucun autre defaut).
    tool_call_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # Horodaté côté Python : `now()` de la base est figé sur la transaction, et
    # sa précision dépend du moteur. Or `created_at` sert à réordonner le
    # journal, où deux messages du même tour ne doivent jamais être ex aequo.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage {self.role} session={self.session_id}>"
