"""Rend leur chance aux archivages tombes a cause du debit, pas de l'URL.

Revision ID: 023_reset_archives
Revises: 022_citations_seen
Create Date: 2026-08-04

Jusqu'ici l'import lancait un archivage par source en parallele. Save Page Now
limite un client anonyme a quelques requetes par minute : sur un import de 152
sources, la quasi-totalite etait jetee, le sondage expirait, et chaque source
etait inscrite `failed` -- un etat terminal que l'interface n'offre aucun moyen
de reprendre. En production, trois fiches sur quatre etaient concernees.

Ces echecs ne disent rien sur les URLs. On les repasse en `pending`, ou la
reprise paresseuse (declenchee au premier affichage de la fiche) les reprendra
a une cadence tenable. Les sources qui ont bel et bien une archive ne sont pas
touchees, et une URL reellement inarchivable (loopback, adresse privee) sera
re-inscrite `failed` des sa premiere reprise par le controle de surete.

Pas de downgrade fidele : on ne sait plus lesquelles etaient `failed` avant. Le
downgrade est donc un no-op assume plutot qu'une remise en echec aveugle qui
detruirait des archives legitimes.
"""

from __future__ import annotations

from alembic import op

revision: str = "023_reset_archives"
down_revision: str | None = "022_citations_seen"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sources
           SET archive_status = 'pending'
         WHERE archive_status = 'failed'
           AND archive_url IS NULL
        """
    )


def downgrade() -> None:
    """No-op : l'information d'origine n'est pas reconstituable."""
