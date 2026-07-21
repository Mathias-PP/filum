"""Add Source.linked_card_id (fiche parente).

Revision ID: 013_source_linked_card
Revises: 012_card_visibility
Create Date: 2026-07-22

Contexte : une source peut pointer vers une autre fiche Philum publique
(URL /@{username}/{slug}). Quand c'est le cas, on stocke l'id de la fiche
liee pour pouvoir afficher un badge "Fiche Philum" et naviguer entre fiches.

La resolution se fait cote serveur a la creation de la source (l'URL n'est
pas modifiable ensuite). Nullable : la grande majorite des sources restent
des URLs externes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013_source_linked_card"
down_revision: str | None = "012_card_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "linked_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("biblio_cards.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_sources_linked_card_id", "sources", ["linked_card_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_linked_card_id", table_name="sources")
    op.drop_column("sources", "linked_card_id")
