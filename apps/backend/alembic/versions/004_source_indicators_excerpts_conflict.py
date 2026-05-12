"""Source indicators, conflicts of interest, excerpts table.

Revision ID: 004_indicators_and_excerpts
Revises: 003_add_parent_source
Create Date: 2026-05-12

Adds structured indicator columns on sources (citations_count,
subscribers_count, views_count, impact_factor) plus an optional
conflict_of_interest text. Replaces the soft judgement carried by
authority_level (kept for backward compatibility, just hidden by the UI).

Also creates the `source_excerpts` table that lets a source carry one
or more verbatim citations. The flag `suggested_by_ai` is future-proof
for the AI excerpt picker.

None of the new fields enter the canonical_hash payload, so existing
signatures remain valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "004_indicators_and_excerpts"
down_revision: str | None = "003_add_parent_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("conflict_of_interest", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("citations_count", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("subscribers_count", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("views_count", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("impact_factor", sa.Float(), nullable=True))

    op.create_table(
        "source_excerpts",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "suggested_by_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("source_excerpts")
    op.drop_column("sources", "impact_factor")
    op.drop_column("sources", "views_count")
    op.drop_column("sources", "subscribers_count")
    op.drop_column("sources", "citations_count")
    op.drop_column("sources", "conflict_of_interest")
