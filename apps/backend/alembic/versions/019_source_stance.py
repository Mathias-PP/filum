"""Ajoute le rapport declare entre une source et le propos.

Revision ID: 019_source_stance
Revises: 018_card_authors
Create Date: 2026-08-03

Une bibliographie dit sur quoi on s'appuie, jamais comment. Un lecteur qui
voit trente sources ne peut pas distinguer celle qui confirme le propos de
celle qui le contredit et que l'auteur cite honnetement. La colonne rend ce
rapport explicite.

Volontairement declarative et nullable : c'est l'auteur de la fiche qui
l'affirme et en repond, aucune inference automatique. Les lignes existantes
restent a NULL -- il n'y a rien a deviner retroactivement.

`String(20)` plutot qu'un type ENUM Postgres : ajouter une valeur a un ENUM
demande un ALTER TYPE hors transaction, la ou le projet fait deja porter la
contrainte par les schemas Pydantic pour `format`, `category` et
`author_kind`.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "019_source_stance"
down_revision: str | None = "018_card_authors"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("stance", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "stance")
