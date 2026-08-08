"""Garder le verdict de relecture, pour que le lecteur puisse le lire.

`/verify` re-ancre chaque extrait dans la source telle qu'elle est aujourd'hui
(migration 033). Ce verdict ne vivait que le temps de la reponse HTTP : la fiche
publique affichait ensuite la citation nue, sans que rien ne distingue un
passage relu ce matin d'un passage jamais verifie. Or c'est exactement la
distinction que Philum existe pour rendre visible -- la garder pour soi revient
a demander au lecteur de croire sur parole.

Les trois colonnes sont **nullables et le restent** : `NULL` veut dire « jamais
relu », et c'est un etat qu'il faut pouvoir afficher comme tel. Le remplir d'une
valeur par defaut ferait passer l'ensemble des extraits existants pour verifies.

`verified_text_source` n'est pas un detail d'implementation : un verdict obtenu
contre la page publique et un verdict obtenu contre un texte fourni par
l'auteur·ice n'engagent pas la meme chose, et l'ecran doit pouvoir le dire.

Revision ID: 034_excerpt_verdict
Revises: 033_excerpt_anchor
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "034_excerpt_verdict"
down_revision: str | None = "033_excerpt_anchor"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("source_excerpts", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.add_column("source_excerpts", sa.Column("verified_status", sa.String(20), nullable=True))
    op.add_column(
        "source_excerpts", sa.Column("verified_text_source", sa.String(20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("source_excerpts", "verified_text_source")
    op.drop_column("source_excerpts", "verified_status")
    op.drop_column("source_excerpts", "verified_at")
