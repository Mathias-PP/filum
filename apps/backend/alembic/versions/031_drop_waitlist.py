"""Supprime la table waitlist_entries.

Revision ID: 031_drop_waitlist
Revises: 030_rls_lockdown

Le bloc « laissez votre email » a ete retire de la page d'accueil le
2026-08-04 : l'inscription Google est ouverte, la promesse faisait doublon.
Seule la visibilite avait ete supprimee, le back-end restait en place.

La note du backlog posait une condition avant toute suppression : verifier
qu'aucune adresse n'avait ete collectee, sous peine de perdre des contacts
reels. Verifie sur la base de production le 2026-08-07 : **0 ligne**. Rien a
exporter, rien a perdre.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_drop_waitlist"
down_revision: str | None = "030_rls_lockdown"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("waitlist_entries")


def downgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("context", sa.String(50), nullable=False, server_default="home"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # NE PAS ajouter d'op.create_index : index=True dans create_table le crée déjà (PITFALLS §1.2)
