"""Add waitlist_entries table.

Revision ID: 009_waitlist
Revises: 008_source_soft_del
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_waitlist"
down_revision: str | None = "008_source_soft_del"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("context", sa.String(50), nullable=False, server_default="home"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # NE PAS ajouter d'op.create_index : index=True dans create_table le crée déjà (PITFALLS §1.2)


def downgrade() -> None:
    op.drop_table("waitlist_entries")
