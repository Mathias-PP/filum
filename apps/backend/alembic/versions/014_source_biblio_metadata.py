"""Add bibliographic metadata columns to sources.

Revision ID: 014_source_biblio_metadata
Revises: 013_source_linked_card
Create Date: 2026-07-22

Contexte : pour des exports bibliographiques de qualite (BibTeX complet,
CSL-JSON Zotero, style APA), une source a besoin des champs classiques
journal / volume / pages / publisher / doi. Tous optionnels — remplis par
l'extraction Crossref ou a la main dans une zone repliable du wizard.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_source_biblio_metadata"
down_revision: str | None = "013_source_linked_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = [
    ("journal", sa.String(300)),
    ("volume", sa.String(50)),
    ("pages", sa.String(50)),
    ("publisher", sa.String(300)),
    ("doi", sa.String(200)),
]


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("sources", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("sources", name)
