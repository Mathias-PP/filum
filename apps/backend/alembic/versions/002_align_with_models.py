"""Align schema with models: add missing columns in biblio_cards and sources.

Revision ID: 002_align_with_models
Revises: 001_initial
Create Date: 2026-05-12

The hand-written 001_initial migration drifted from the SQLAlchemy models
(slug, platform, signed_at on biblio_cards; position, authors, published_at,
is_pivot on sources). Production deploy on Railway exposed this when the demo
seed tried to query biblio_cards.slug. This migration brings the schema back
in line so the ORM queries succeed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_align_with_models"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column(
            "slug",
            sa.String(100),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index("ix_biblio_cards_slug", "biblio_cards", ["slug"])
    op.add_column(
        "biblio_cards",
        sa.Column(
            "platform",
            sa.String(50),
            nullable=False,
            server_default="other",
        ),
    )
    op.add_column(
        "biblio_cards",
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_biblio_cards_user_status", "biblio_cards", ["user_id", "status"]
    )

    op.add_column(
        "sources",
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sources",
        sa.Column("authors", sa.String(500), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column(
            "is_pivot",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("sources", "is_pivot")
    op.drop_column("sources", "published_at")
    op.drop_column("sources", "authors")
    op.drop_column("sources", "position")
    op.drop_index("ix_biblio_cards_user_status", table_name="biblio_cards")
    op.drop_column("biblio_cards", "signed_at")
    op.drop_column("biblio_cards", "platform")
    op.drop_index("ix_biblio_cards_slug", table_name="biblio_cards")
    op.drop_column("biblio_cards", "slug")
