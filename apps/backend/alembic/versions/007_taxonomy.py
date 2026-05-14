"""Replace source_type/authority_level with format/category/author_kind.

Revision ID: 007_taxonomy
Revises: 006_content_attestations
Create Date: 2026-05-14

Implements ADR-020: source taxonomy refactored into 3 orthogonal axes.
Pre-MVP, so a best-effort backfill is acceptable; the seed is rewritten
with the real values and dev accounts can edit any leftover rows.

Mapping applied during upgrade:

  source_type    → format / category            / author_kind
  peer-reviewed  → texte  / article-scientifique / chercheur
  institutional  → texte  / communique           / institution-publique
  press          → texte  / article-presse       / media
  video          → video  / documentaire         / media
  image          → image  / page-web             / individu
  original       → texte  / notes                / individu
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_taxonomy"
down_revision: str | None = "006_content_attestations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Add new columns nullable (so backfill can run on existing rows)
    op.add_column("sources", sa.Column("format", sa.String(20), nullable=True))
    op.add_column("sources", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("sources", sa.Column("author_kind", sa.String(40), nullable=True))

    # 2) Backfill from legacy source_type. Pre-MVP heuristic mapping.
    op.execute(
        """
        UPDATE sources SET
            format = CASE source_type
                WHEN 'video' THEN 'video'
                WHEN 'image' THEN 'image'
                ELSE 'texte'
            END,
            category = CASE source_type
                WHEN 'peer-reviewed' THEN 'article-scientifique'
                WHEN 'institutional' THEN 'communique'
                WHEN 'press'         THEN 'article-presse'
                WHEN 'video'         THEN 'documentaire'
                WHEN 'image'         THEN 'page-web'
                WHEN 'original'      THEN 'notes'
                ELSE 'page-web'
            END,
            author_kind = CASE source_type
                WHEN 'peer-reviewed' THEN 'chercheur'
                WHEN 'institutional' THEN 'institution-publique'
                WHEN 'press'         THEN 'media'
                WHEN 'video'         THEN 'media'
                WHEN 'image'         THEN 'individu'
                WHEN 'original'      THEN 'individu'
                ELSE 'individu'
            END
        """
    )

    # 3) Lock the columns NOT NULL now that they are populated
    op.alter_column("sources", "format", nullable=False)
    op.alter_column("sources", "category", nullable=False)
    op.alter_column("sources", "author_kind", nullable=False)

    # 4) Index on author_kind (queried/grouped frequently for graph rendering).
    # ix_sources_author_kind matches the auto-name SQLAlchemy would generate
    # from Column(index=True) on the model so downgrade cascades cleanly.
    op.create_index(
        "ix_sources_author_kind",
        "sources",
        ["author_kind"],
    )

    # 5) Drop legacy columns + their auto-indexes (cascaded)
    op.drop_column("sources", "source_type")
    op.drop_column("sources", "authority_level")


def downgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("authority_level", sa.String(20), nullable=False, server_default="medium"),
    )
    op.add_column(
        "sources",
        sa.Column("source_type", sa.String(50), nullable=True),
    )

    # Best-effort reverse mapping (lossy: author_kind+category collapse into one bucket)
    op.execute(
        """
        UPDATE sources SET source_type = CASE
            WHEN author_kind = 'chercheur'             THEN 'peer-reviewed'
            WHEN author_kind = 'institution-publique'  THEN 'institutional'
            WHEN author_kind = 'media' AND format = 'video' THEN 'video'
            WHEN author_kind = 'media'                 THEN 'press'
            WHEN format = 'image'                      THEN 'image'
            ELSE 'original'
        END
        """
    )
    op.alter_column("sources", "source_type", nullable=False)

    op.drop_index("ix_sources_author_kind", table_name="sources")
    op.drop_column("sources", "author_kind")
    op.drop_column("sources", "category")
    op.drop_column("sources", "format")
