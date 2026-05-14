"""Create content_attestations table, drop card signature columns.

Revision ID: 006_content_attestations
Revises: 005_nullable_card_hash_sig
Create Date: 2026-05-14

Implements ADR-019: signatures move from card-level to per-content
attestations.  The triplet (creator_id, content_url, attested_at) is
what gets signed with Ed25519.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_content_attestations"
down_revision: str | None = "005_nullable_card_hash_sig"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_attestations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content_url", sa.String(1000), nullable=False),
        sa.Column("attested_at", sa.DateTime(), nullable=False),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_attestations_user_url",
        "content_attestations",
        ["user_id", "content_url"],
    )
    op.create_index(
        op.f("ix_content_attestations_user_id"),
        "content_attestations",
        ["user_id"],
    )

    # Drop card-level signature fields (replaced by content_attestations)
    # Note: ix_biblio_cards_canonical was never created in migrations (only in
    # the model's __table_args__). The auto-index ix_biblio_cards_canonical_hash
    # from Column(index=True) in 001_initial will cascade-drop with the column.
    op.drop_column("biblio_cards", "canonical_hash")
    op.drop_column("biblio_cards", "signature")
    op.drop_column("biblio_cards", "signed_at")


def downgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column("signed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "biblio_cards",
        sa.Column("signature", sa.Text(), nullable=True),
    )
    op.add_column(
        "biblio_cards",
        sa.Column("canonical_hash", sa.String(64), nullable=True),
    )
    # Note: the original Column(index=True) in 001_initial auto-generated
    # ix_biblio_cards_canonical_hash. We re-create that index here for
    # downgrade correctness.
    op.create_index(
        "ix_biblio_cards_canonical_hash",
        "biblio_cards",
        ["canonical_hash"],
    )
    op.drop_index(
        op.f("ix_content_attestations_user_id"),
        table_name="content_attestations",
    )
    op.drop_index(
        "ix_content_attestations_user_url",
        table_name="content_attestations",
    )
    op.drop_table("content_attestations")
