from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.excerpt_embedding import EMBEDDING_TYPE


class GraphEntity(Base):
    """Noeud du graphe memoire (STARTER: 3 tables).

    Identite hachee uuid5(type + normalise(name)) — deux fiches qui
    parlent du meme concept partagent le meme noeud, sans ML.
    """

    __tablename__ = "graph_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_card_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("biblio_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(EMBEDDING_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=sa.func.now())


class GraphRelation(Base):
    """Arete typee portant sa fiche source (traçabilité)."""

    __tablename__ = "graph_relations"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_card_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("biblio_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )


class GraphAlias(Base):
    """Variante de nom (Warburg -> Effet Warburg)."""

    __tablename__ = "graph_aliases"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
