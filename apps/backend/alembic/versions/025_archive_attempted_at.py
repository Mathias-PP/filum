"""Dater la tentative d'archivage, distinctement de la capture.

Mesure en prod le 2026-08-04 : une fiche restait a 132 sources `pending`
malgre six passes de reprise. Le lot est borne par un budget de temps et la
liste lui etait toujours servie dans le meme ordre : les sources situees apres
la frontiere n'etaient donc **jamais atteintes** -- pas « plus tard », jamais.
Verifie en resolvant un echantillon a la main : plusieurs avaient une capture
`200` disponible a l'instant meme.

`archive_attempted_at` (quand on a essaye) et `archive_timestamp` (quand la
capture a ete faite) sont deux faits distincts. Les confondre reintroduirait
l'erreur que corrige toute cette serie.

NULL = jamais tente, et c'est ce qui passe en premier : les lignes existantes
n'ont pas a etre retro-datees.

Revision ID: 025_archive_try
Revises: 024_archive_na
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "025_archive_try"
down_revision: str | None = "024_archive_na"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("archive_attempted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "archive_attempted_at")
