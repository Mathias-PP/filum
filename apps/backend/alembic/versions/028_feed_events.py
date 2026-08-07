"""Feed chronologique public : une trace, pas un reseau social.

Chaque entree enregistre qu'une fiche a ete publiee a une date, par un
createur donne. Immuable : si la fiche est ensuite depubliee, l'entree
reste (avec un champ `unpublished_at` non nul), meme logique que
l'attestation de contenu (ADR-019). Voir `.docs/20-profils-et-feed.md`.

`kind` en varchar plutot qu'un enum : les evolutions (`card_updated`,
`claim_verified`) doivent pouvoir arriver sans migration structurelle.

Revision ID: 028_feed_events
Revises: 027_link_prov
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "028_feed_events"
down_revision: str | None = "027_link_prov"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "feed_events",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column(
            "actor_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "card_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("biblio_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("unpublished_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_feed_events_kind_occurred",
        "feed_events",
        ["kind", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feed_events_kind_occurred", table_name="feed_events")
    op.drop_table("feed_events")
