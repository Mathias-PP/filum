"""Add BiblioCard.visibility (public | private).

Revision ID: 012_card_visibility
Revises: 011_linked_accounts
Create Date: 2026-07-21

Contexte : une fiche publiee etait jusqu'ici toujours accessible publiquement.
On ajoute une distinction produit :
  - visibility='public'  -> visible par tout le monde (comportement actuel).
  - visibility='private' -> visible uniquement par son owner connecte.

DB default = 'public' pour que toutes les fiches existantes conservent leur
comportement actuel apres migration. Le choix explicite se fait a la creation
via le champ CardCreate.visibility (default 'public').
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_card_visibility"
down_revision: str | None = "011_linked_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="public",
        ),
    )


def downgrade() -> None:
    op.drop_column("biblio_cards", "visibility")
