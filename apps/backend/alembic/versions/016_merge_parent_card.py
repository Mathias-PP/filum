"""Fusionne Source.parent_card_id dans Source.linked_card_id.

Revision ID: 016_merge_parent_card
Revises: 015_source_parent_card
Create Date: 2026-07-30

La migration 015 avait introduit `parent_card_id` comme lien de hierarchie
distinct de `linked_card_id`. En pratique la distinction n'avait aucun
consommateur : le picker de l'interface ecrivait `parent_card_id`, que rien
ne lisait, tandis que le meta-graphe et la constellation lisaient
`linked_card_id`, que seule une URL Philum collee pouvait remplir. Resultat
en prod : 2 lignes cote picker, 0 cote graphe, et aucune meta-fiche possible.

On garde un seul concept — "cette source designe cette fiche Philum" — porte
par `linked_card_id`, alimente soit par le picker soit par l'URL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "016_merge_parent_card"
down_revision: str | None = "015_source_parent_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Les liens choisis au picker deviennent de vrais liens de meta-graphe.
    op.execute(
        """
        UPDATE sources
        SET linked_card_id = parent_card_id
        WHERE parent_card_id IS NOT NULL AND linked_card_id IS NULL
        """
    )
    op.drop_index("ix_sources_parent_card_id", table_name="sources")
    op.drop_column("sources", "parent_card_id")


def downgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "parent_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("biblio_cards.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_sources_parent_card_id", "sources", ["parent_card_id"])
