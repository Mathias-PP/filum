"""Donner a un extrait de quoi etre retrouve dans une source qui a bouge.

Un extrait ne porte aujourd'hui que son texte. Le retrouver, c'est le chercher
au mot pres -- et une page qui corrige une coquille ou change de gabarit fait
echouer cette recherche. L'extrait devient alors indiscernable d'une citation
inventee, ce que Philum existe precisement pour eliminer.

On stocke donc, selon la specification publique d'Hypothes.is, deux selecteurs
de plus pour la meme cible : le voisinage immediat du passage, qui departage
deux occurrences identiques, et sa position d'origine, qui n'est qu'un indice.

Les trois colonnes sont **nullables et le restent** : les extraits deja saisis
n'ont pas de selecteurs, et aucune valeur inventee ne vaut mieux que l'absence.
Un extrait sans ancrage se lit comme non verifiable, pas comme verifie.

Revision ID: 033_excerpt_anchor
Revises: 032_excerpt_title
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "033_excerpt_anchor"
down_revision: str | None = "032_excerpt_title"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("source_excerpts", sa.Column("anchor_prefix", sa.Text(), nullable=True))
    op.add_column("source_excerpts", sa.Column("anchor_suffix", sa.Text(), nullable=True))
    op.add_column("source_excerpts", sa.Column("anchor_offset", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_excerpts", "anchor_offset")
    op.drop_column("source_excerpts", "anchor_suffix")
    op.drop_column("source_excerpts", "anchor_prefix")
