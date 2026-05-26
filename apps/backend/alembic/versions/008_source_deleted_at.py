"""Add deleted_at on sources (soft-delete).

Revision ID: 008_source_soft_del
Revises: 007_taxonomy
Create Date: 2026-05-26

Audit phase 4 (2026-05-26): BiblioCard already had ``deleted_at`` via
migration 001 (unused — no query filtered on it), and User has one via
TimestampMixin. Source had neither. This migration adds the column on
sources so the API DELETE handlers can switch from a hard DELETE to a
soft delete, preserving citations history and giving an "undo" runway.

The column is nullable and indexed (queries always filter
``deleted_at IS NULL`` on the public path). No backfill needed: existing
rows are by definition live so their ``deleted_at`` is correctly NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision id stays ≤ 32 chars per PITFALLS §1.1.
revision: str = "008_source_soft_del"
down_revision: str | None = "007_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_sources_deleted_at",
        "sources",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sources_deleted_at", table_name="sources")
    op.drop_column("sources", "deleted_at")
