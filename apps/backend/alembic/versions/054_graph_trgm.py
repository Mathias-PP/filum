"""Graphe : index trigram pour recall <50ms.

Revision ID: 054_graph_trgm
Revises: 053_graph_memory
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "054_graph_trgm"
down_revision: str | None = "053_graph_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_graph_entities_name_trgm ON graph_entities USING gin (lower(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_graph_aliases_alias_trgm ON graph_aliases USING gin (lower(alias) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_graph_aliases_alias_trgm")
    op.execute("DROP INDEX IF EXISTS ix_graph_entities_name_trgm")
