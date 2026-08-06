"""Tracer d'ou vient un lien fiche a fiche, et s'il a ete valide.

Trois chemins ecrivaient `linked_card_id` sans laisser de trace : le
selecteur, l'URL Philum collee, et la deduction par DOI ou URL equivalente.
Le troisieme est une hypothese, les deux premiers sont des gestes. Les
confondre rendait impossible tout espace de gestion : on ne peut pas proposer
de retirer une suggestion qu'on ne sait pas reconnaitre.

`link_confirmed_at` NULL = jamais confirme par un humain. Les liens existants
ne sont pas retro-confirmes : personne ne les a valides, l'affirmer serait
faux. Ils gardent `link_origin` NULL, qui dit « on ne sait pas ».

Revision ID: 027_link_prov
Revises: 026_card_ref
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "027_link_prov"
down_revision: str | None = "026_card_ref"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("link_origin", sa.String(20), nullable=True))
    op.add_column("sources", sa.Column("link_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "link_confirmed_at")
    op.drop_column("sources", "link_origin")
