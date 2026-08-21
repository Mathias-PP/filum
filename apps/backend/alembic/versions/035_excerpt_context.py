"""Une mise en situation par extrait, distincte du verbatim.

Un extrait voyage : il part dans un export, dans une reponse MCP, dans la
fiche publique, et il y arrive seul. « Ce modele distingue trois composantes »
ne nomme ni son auteur, ni son objet, ni le texte d'ou il vient. La phrase de
mise en situation restitue ces reperes.

Elle est stockee a cote du verbatim, jamais dedans. Concatener les deux ferait
attribuer a la source une phrase qu'elle n'a pas ecrite — exactement ce que
Philum existe pour empecher. `annotated_by_ai` dit si cette phrase, ou
l'intitule, viennent d'un modele.

Revision ID: 035_excerpt_context
Revises: 034_excerpt_verdict
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "035_excerpt_context"
down_revision: str | None = "034_excerpt_verdict"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_excerpts", sa.Column("context", sa.String(500), nullable=True))
    op.add_column(
        "source_excerpts",
        sa.Column(
            "annotated_by_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("source_excerpts", "annotated_by_ai")
    op.drop_column("source_excerpts", "context")
