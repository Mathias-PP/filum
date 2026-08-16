"""L'extension `unaccent`, pour que « memoire » trouve « Mémoire ».

La recherche de fiches, la recherche de créateurs et l'outil MCP
`search_cards` comparaient un motif à un titre par simple sous-chaîne. Sur un
corpus francophone, cela veut dire qu'aucune de ces trois surfaces ne répond à
un motif tapé sans accent, alors que c'est la façon dont on tape vite, et la
seule dont un agent qui a lu un titre translittéré peut le redemander.

`unaccent()` n'est pas marquée IMMUTABLE : elle n'entre donc pas dans un index
et ne sert qu'au parcours. À l'échelle du corpus actuel, c'est sans effet
mesurable ; le jour où ça compte, la voie est un index d'expression sur un
wrapper IMMUTABLE, pas un changement de cette migration.

Revision ID: 037_unaccent
Revises: 036_excerpt_embeddings
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "037_unaccent"
down_revision: str | None = "036_excerpt_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # L'extension n'est pas supprimée : d'autres objets peuvent en dépendre, et
    # la laisser en place ne coûte rien. Le code qui l'appelle sait s'en passer.
    pass
