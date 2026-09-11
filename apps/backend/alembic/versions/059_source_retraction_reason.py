"""Une source retractee peut dire pourquoi.

Crossref rend le fait de la retractation, jamais sa cause. La cause vient du
jeu Retraction Watch, publie par Crossref sous CC BY 4.0 en un fichier unique
et sans interrogation par DOI : elle ne peut donc pas etre remplie par la meme
passe que le statut, et arrive par `app.scripts.motifs_retractation`.

`Text` et non `String(200)` : le champ est une liste de tags separes par des
points-virgules, et la plus longue observee au 2026-09-11 fait 511 caracteres.

`NULL` se lit « motif inconnu ici ». Un avis qui ne motive rien n'est pas ce
cas-la : Retraction Watch l'ecrit « Notice - Limited or No Information », et
cette chaine-la se stocke comme les autres.

Revision ID: 059_source_retraction_reason
Revises: 058_source_metadata_origin
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "059_source_retraction_reason"
down_revision: str | None = "058_source_metadata_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("retraction_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "retraction_reason")
