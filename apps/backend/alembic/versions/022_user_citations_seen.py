"""Marque la derniere consultation des citations entrantes.

Revision ID: 022_citations_seen
Revises: 021_source_oa
Create Date: 2026-08-03

Une fiche citee par une autre fiche Philum est un signal de reprise : c'est la
seule chose que le createur ne peut pas apprendre en regardant ses propres
donnees. Encore faut-il pouvoir distinguer ce qui est nouveau de ce qui a deja
ete vu.

``citations_seen_at`` est NULLABLE a dessein, et NULL ne veut pas dire « rien de
nouveau » : il veut dire « jamais consulte ». Dans ce cas toutes les citations
entrantes comptent comme nouvelles, ce qui est la lecture honnete -- personne
n'a encore regarde. Mettre ``now()`` par defaut effacerait silencieusement
l'historique de reprise deja accumule.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "022_citations_seen"
down_revision: str | None = "021_source_oa"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("citations_seen_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "citations_seen_at")
