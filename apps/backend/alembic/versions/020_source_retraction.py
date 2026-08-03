"""Ajoute l'etat de retractation d'une source, verifie via Crossref.

Revision ID: 020_source_retraction
Revises: 019_source_stance
Create Date: 2026-08-03

Une bibliographie qui cite un article retracte le cite pour toujours : ni le
lecteur ni l'auteur de la fiche n'ont de moyen de l'apprendre une fois la
video publiee. Crossref agrege Retraction Watch et expose les avis sur
``works/{doi}``.

Trois colonnes plutot qu'une, parce que trois etats doivent rester
distinguables :

- ``retraction_status`` NULL      : jamais verifie ;
- ``retraction_status`` = none    : Crossref connait le DOI et ne signale rien ;
- ``retraction_status`` = unverifiable : pas de DOI, DOI inconnu, service muet.

``retraction_checked_at`` date la deuxieme affirmation : « aucun avis » sans
date serait une promesse que rien ne soutient. ``retraction_notice_doi``
laisse le lecteur aller lire l'avis lui-meme.

Aucune valeur retroactive : les lignes existantes restent a NULL et seront
verifiees a la demande.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "020_source_retraction"
down_revision: str | None = "019_source_stance"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("retraction_status", sa.String(length=20), nullable=True))
    op.add_column(
        "sources", sa.Column("retraction_notice_doi", sa.String(length=200), nullable=True)
    )
    op.add_column("sources", sa.Column("retraction_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "retraction_checked_at")
    op.drop_column("sources", "retraction_notice_doi")
    op.drop_column("sources", "retraction_status")
