"""Colonne `content_text` pour porter le texte integral du contenu documente.

Beaucoup de créateurs travaillent sur un contenu dont ils ont le texte : leur
propre article, un contenu libre de droit, une retranscription qu'ils ont
faite, ou un extrait qu'ils ont le droit de citer. Sans un endroit ou le
poser, ils devaient soit renoncer, soit le mettre dans une source, ce qui
melangeait « le contenu que la fiche documente » avec « les references qu'il
cite » — deux choses distinctes qu'aucune vue ne pouvait plus separer.

Le champ est nullable et sans borne de longueur cote colonne : PostgreSQL
`TEXT` accepte le TOAST jusqu'a 1 Go, la borne pratique (quelques Mo) est
posee cote endpoint. Aucun index : la recherche par le texte du contenu
suppose deja les embeddings d'extraits (services/excerpt_search.py) et
regexer 200 fiches full-text a chaud n'aurait pas d'utilisateur.

Revision ID: 038_content_text
Revises: 037_unaccent
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "038_content_text"
down_revision: str | None = "037_unaccent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("biblio_cards", sa.Column("content_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("biblio_cards", "content_text")
