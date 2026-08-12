"""Vecteurs des extraits, pour la recherche semantique.

La table vit a cote de `source_excerpts` et non dedans : changer de modele
d'embedding doit pouvoir se faire en ecrivant la nouvelle serie a cote de
l'ancienne, puis en basculant, sans verrou sur une table lue a chaque
affichage de fiche.

Aucun index de similarite ici, volontairement. En dessous de quelques dizaines
de milliers de vecteurs, un parcours sequentiel repond en quelques
millisecondes et donne un rappel exact, la ou HNSW est approximatif et coute
de la memoire a la construction. L'index sera une migration a lui seul, le
jour ou le volume le demande : `CREATE INDEX CONCURRENTLY` ne reecrit pas la
table.

Revision ID: 036_excerpt_embeddings
Revises: 035_excerpt_context
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036_excerpt_embeddings"
down_revision: str | None = "035_excerpt_context"
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
    # Sans `WITH SCHEMA`, l'extension atterrit dans le premier schema du
    # search_path, qui n'est pas garanti. Le type doit etre joignable non
    # qualifie : les casts `::vector` emis a l'execution ne portent pas de
    # schema.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")

    schema = _schema_du_type_vector(conn)
    if schema is None:
        raise RuntimeError(
            "pgvector n'est pas disponible sur cette base. "
            "Sur Supabase : Database > Extensions > activer `vector`."
        )
    if schema != "public":
        # `CREATE EXTENSION IF NOT EXISTS` est un no-op quand l'extension
        # existe deja ailleurs : le `WITH SCHEMA` ci-dessus a ete ignore. On
        # s'arrete plutot que de creer une table dont les requetes echoueront
        # a l'execution, loin d'ici et sans rapport apparent.
        raise RuntimeError(
            f"pgvector est installe dans le schema `{schema}`, or les casts "
            "`::vector` emis par l'application ne sont pas qualifies. "
            "Corriger avec : ALTER EXTENSION vector SET SCHEMA public;"
        )

    op.create_table(
        "excerpt_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "excerpt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_excerpts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("model", sa.String(80), nullable=False, index=True),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        # Cree en tableau de reels puis converti : `sa.Column` ne connait pas
        # le type `vector`, et importer pgvector ici lierait le dossier des
        # migrations a une dependance applicative.
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("excerpt_id", "model", name="uq_excerpt_embedding_model"),
    )
    op.execute(
        f"ALTER TABLE excerpt_embeddings ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM})"
    )

    # Meme verrou que la migration 030 : Supabase expose `public` en REST et la
    # cle `anon` est publique par conception.
    op.execute("ALTER TABLE public.excerpt_embeddings ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("excerpt_embeddings")
