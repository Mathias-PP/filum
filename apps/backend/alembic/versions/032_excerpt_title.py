"""Donner un intitule a un extrait, pour qu'il se situe sans etre lu en entier.

Une fiche affiche jusqu'a dix extraits par source, chacun pouvant faire
plusieurs centaines de caracteres. Empiles sans intitule, ils obligent a tout
lire pour trouver le passage cherche -- alors que l'auteur·ice, elle, sait
pourquoi elle a retenu chacun.

`title` est **nullable et le reste** : imposer un intitule ferait inventer une
etiquette la ou il n'y a rien a dire, et un intitule faux vaut moins que pas
d'intitule (regle tenue en #317, #323, #327).

Revision ID: 032_excerpt_title
Revises: 031_drop_waitlist
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "032_excerpt_title"
down_revision: str | None = "031_drop_waitlist"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("source_excerpts", sa.Column("title", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("source_excerpts", "title")
