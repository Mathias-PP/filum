"""Ajoute l'etat d'acces libre d'une source, verifie via OpenAlex.

Revision ID: 021_source_oa
Revises: 020_source_retraction
Create Date: 2026-08-03

Une bibliographie qui renvoie a un article sous paywall arrete le lecteur net,
alors qu'une large part de ces articles a une version legalement gratuite
ailleurs. OpenAlex agrege ces routes sur ``works/doi:{doi}``.

Meme regle a trois etats que pour les retractations :

- ``oa_status`` NULL           : jamais verifie ;
- ``oa_status`` = closed       : OpenAlex connait la reference, rien de gratuit ;
- ``oa_status`` = unverifiable : pas de DOI, DOI inconnu, service muet.

``in_doaj`` est un booleen NULLABLE a dessein : NULL = OpenAlex ne dit rien.
Un ``False`` par defaut affirmerait que la revue n'est pas referencee au DOAJ,
ce que personne n'a verifie.

Aucune valeur retroactive : les lignes existantes restent a NULL et seront
verifiees a la demande.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "021_source_oa"
down_revision: str | None = "020_source_retraction"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("oa_status", sa.String(length=20), nullable=True))
    op.add_column("sources", sa.Column("oa_url", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("oa_license", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("in_doaj", sa.Boolean(), nullable=True))
    op.add_column("sources", sa.Column("oa_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "oa_checked_at")
    op.drop_column("sources", "in_doaj")
    op.drop_column("sources", "oa_license")
    op.drop_column("sources", "oa_url")
    op.drop_column("sources", "oa_status")
