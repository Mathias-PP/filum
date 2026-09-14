"""Synthese ancree d'une fiche.

Une colonne texte sur `biblio_cards`. Chaque phrase y finit par ses renvois
`[extrait:<id>]` vers les extraits verbatim de la fiche ; la verification
(chaque phrase renvoie a un extrait de la fiche qui la soutient) est faite avant
l'ecriture, dans `services/synthese.py`, pas par une contrainte de base : elle
demande de lire les extraits et, quand ils repondent, les embeddings.

`NULL` se lit « pas de synthese », etat normal d'une fiche.

Revision ID: 061_synthese_ancree
Revises: 060_fidelite_des_extraits
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "061_synthese_ancree"
down_revision: str | None = "060_fidelite_des_extraits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("biblio_cards", sa.Column("synthese", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("biblio_cards", "synthese")
