"""Make biblio_cards.canonical_hash and .signature nullable (drafts).

Revision ID: 005_nullable_card_hash_sig
Revises: 004_indicators_and_excerpts
Create Date: 2026-05-13

The 001_initial migration created `canonical_hash` and `signature` as
NOT NULL, but `CardService.create_card()` creates draft cards without
setting them. This contradiction was invisible until tests exercised
the path: any user-driven `POST /cards` would crash on insert.

Loosens both columns to nullable. They are set by `publish_card()` when
the user publishes. The SQLAlchemy model declaration is updated in the
same PR (apps/backend/app/models/biblio_card.py).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_nullable_card_hash_sig"
down_revision: str | None = "004_indicators_and_excerpts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("biblio_cards") as batch_op:
        batch_op.alter_column("canonical_hash", existing_type=sa.String(64), nullable=True)
        batch_op.alter_column("signature", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Re-tightening to NOT NULL would fail on any draft rows.
    # Backfill empty strings first, then alter back.
    with op.batch_alter_table("biblio_cards") as batch_op:
        batch_op.execute("UPDATE biblio_cards SET canonical_hash = '' WHERE canonical_hash IS NULL")
        batch_op.execute("UPDATE biblio_cards SET signature = '' WHERE signature IS NULL")
        batch_op.alter_column("canonical_hash", existing_type=sa.String(64), nullable=False)
        batch_op.alter_column("signature", existing_type=sa.Text(), nullable=False)
