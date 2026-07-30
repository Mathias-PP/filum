"""Add Source.parent_card_id (meta-fiches).

Revision ID: 015_source_parent_card
Revises: 014_source_biblio_metadata
Create Date: 2026-07-30

Contexte : une source peut deja avoir pour parent une autre source de la
meme fiche (`parent_source_id`). On veut aussi pouvoir rattacher une source
a une FICHE entiere : c'est ce qui permet les "meta-fiches", ou une fiche
agrege le travail d'autres fiches.

A ne pas confondre avec `linked_card_id`, qui signifie "cette source EST
cette fiche" (resolu automatiquement quand l'URL matche /@{user}/{slug}).
Ici il s'agit d'un lien de hierarchie choisi explicitement par l'auteur.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "015_source_parent_card"
down_revision: str | None = "014_source_biblio_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_sources_parent_card_id", table_name="sources")
    op.drop_column("sources", "parent_card_id")
