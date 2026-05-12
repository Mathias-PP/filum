"""Add parent_source_id to sources for citation graph.

Revision ID: 003_add_parent_source
Revises: 002_align_with_models
Create Date: 2026-05-12

A source may now point to another source on the same card that it cites
("source of source"). The relationship is matched in the SQLAlchemy model
as Source.parent / Source.parent_source_id and is purely structural — it
does NOT enter the canonical_hash that signs a card, so existing
signatures remain valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "003_add_parent_source"
down_revision: str | None = "002_align_with_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "parent_source_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sources_parent_source_id",
        "sources",
        ["parent_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sources_parent_source_id", table_name="sources")
    op.drop_column("sources", "parent_source_id")
