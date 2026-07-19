"""Add linked_accounts table (comptes plateformes lies, v0).

Revision ID: 011_linked_accounts
Revises: 010_claim_requests
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_linked_accounts"
down_revision: str | None = "010_claim_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "linked_accounts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("handle", sa.String(100), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verification_method", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "platform", "url"),
    )
    # index=True dans create_table suffit — pas de create_index (PITFALLS §1.2)


def downgrade() -> None:
    op.drop_table("linked_accounts")
