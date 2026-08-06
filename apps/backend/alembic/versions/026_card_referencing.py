"""Aligner les fiches sur les options de referencement de leurs sources.

Une fiche est une reference comme une autre des qu'une autre fiche la cite :
elle a un format, une categorie et un type d'auteur. Sans ces colonnes, un
noeud fiche restait d'une seule couleur quel que soit le mode de lecture du
graphe, et sortait de la grille de lecture au moment ou le lecteur en avait le
plus besoin.

Les trois colonnes sont NULLABLE, contrairement a `sources` : NULL veut dire
« pas declare », pas « autre ». Retro-remplir depuis `content_type` aurait
invente une declaration que personne n'a faite.

Revision ID: 026_card_ref
Revises: 025_archive_try
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "026_card_ref"
down_revision: str | None = "025_archive_try"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("biblio_cards", sa.Column("format", sa.String(20), nullable=True))
    op.add_column("biblio_cards", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("biblio_cards", sa.Column("author_kind", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("biblio_cards", "author_kind")
    op.drop_column("biblio_cards", "category")
    op.drop_column("biblio_cards", "format")
