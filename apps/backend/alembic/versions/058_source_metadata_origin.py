"""Une source dit qui a fait foi pour ses metadonnees.

Le titre, les auteurs, la date, la revue et l'editeur d'une source ne sont plus
saisis par l'agent mais rendus par un resolveur qu'il designe. Cette colonne
garde la trace du resolveur retenu, sans quoi personne ne peut distinguer plus
tard un titre lu sur Crossref d'un titre dicte par le createur.

`NULL` se lit « origine inconnue » : la ligne a ete posee avant que la regle
existe. Ne jamais retro-remplir cette colonne, ce serait affirmer une origine
qu'on ignore. Pas de contrainte d'enum en base : les valeurs sont validees a
l'ecriture, et une contrainte ici obligerait une migration a chaque origine
nouvelle.

Revision ID: 058_source_metadata_origin
Revises: 057_lane_secours_modele_distinct
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "058_source_metadata_origin"
down_revision: str | None = "057_lane_secours_modele_distinct"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("metadata_origin", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "metadata_origin")
