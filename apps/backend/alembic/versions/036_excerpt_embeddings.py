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

Le type est qualifie par le schema ou l'extension se trouve reellement. A
l'execution en revanche, l'operateur de distance `<=>` est resolu par le
search_path de la session : si pgvector vit hors de `public`, la requete de
similarite devra le verifier le jour ou elle sera ecrite.

Revision ID: 036_excerpt_embeddings
Revises: 035_excerpt_context
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Ou l'extension a atterri n'est pas notre affaire. Sur une base nue elle
    # va dans `public` ; sur Supabase elle est souvent deja la, dans le schema
    # `extensions`, et `CREATE EXTENSION IF NOT EXISTS` est alors un no-op qui
    # ignore tout `WITH SCHEMA`. Imposer `public` reviendrait a faire echouer
    # la migration au demarrage du backend, donc a le mettre en boucle de
    # redemarrage, pour une contrainte qu'on peut simplement lever en
    # qualifiant le type.
    schema = _schema_du_type_vector(conn)
    if schema is None:
        raise RuntimeError(
            "pgvector n'est pas disponible sur cette base. "
            "Sur Supabase : Database > Extensions > activer `vector`."
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
        f"ALTER TABLE excerpt_embeddings "
        f"ALTER COLUMN embedding TYPE {schema}.vector({EMBEDDING_DIM})"
    )

    # Meme verrou que la migration 030 : Supabase expose `public` en REST et la
    # cle `anon` est publique par conception.
    op.execute("ALTER TABLE public.excerpt_embeddings ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("excerpt_embeddings")
