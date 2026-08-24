"""Graphe memoire STARTER : 3 tables, 1 requete recursive, 1 hook.

Identite hachee uuid5(type+name), relations typees, aliases.
Voir Glitch-Cat-Club/graph-memory-starter (3 tables, 1 recursive query, 1 prompt hook).
Revision ID: 053_graph_memory
Revises: 052_lane_zai_secours
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "053_graph_memory"
down_revision: str | None = "052_lane_zai_secours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 768


def _schema_du_type_vector(conn) -> str | None:
    row = conn.exec_driver_sql(
        "SELECT n.nspname FROM pg_type t "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE t.typname = 'vector'"
    ).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    schema = _schema_du_type_vector(conn)
    if schema is None:
        raise RuntimeError("pgvector n'est pas disponible. Activer l'extension vector.")

    op.create_table(
        "graph_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("type", sa.String(30), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("biblio_cards.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute(f"ALTER TABLE graph_entities ALTER COLUMN embedding TYPE {schema}.vector({EMBEDDING_DIM})")

    op.create_table(
        "graph_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("predicate", sa.String(40), nullable=False, index=True),
        sa.Column("source_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("biblio_cards.id", ondelete="SET NULL"), nullable=True, index=True),
    )

    op.create_table(
        "graph_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("graph_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("alias", sa.String(300), nullable=False, index=True),
    )

    op.execute("ALTER TABLE public.graph_entities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.graph_relations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.graph_aliases ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("graph_aliases")
    op.drop_table("graph_relations")
    op.drop_table("graph_entities")
