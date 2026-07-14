"""Add is_seed on biblio_cards + claim_requests table.

Revision ID: 010_claim_requests
Revises: 009_waitlist
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_claim_requests"
down_revision: str | None = "009_waitlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "claim_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "card_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("biblio_cards.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("channel_url", sa.String(1000), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # index=True dans create_table suffit — pas de create_index (PITFALLS §1.2)


def downgrade() -> None:
    op.drop_table("claim_requests")
    op.drop_column("biblio_cards", "is_seed")
