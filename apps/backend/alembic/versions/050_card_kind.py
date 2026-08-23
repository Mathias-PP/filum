"""Nature d'une fiche : documente un contenu, ou porte une bibliographie.

Jusqu'ici toute fiche devait declarer `platform` et `content_type`, donc toute
fiche pretendait documenter un contenu existant. Une bibliographie sur un
sujet n'avait pas de case : elle finissait en `content_type='article'` avec un
`content_authors` invente, c'est a dire en fiche qui documente un article qui
n'existe pas.

`card_kind` tranche : `contenu` documente une video, un article, un post, qui
ont une URL et des auteurs ; `sujet` porte une bibliographie sur une question,
dont le createur Philum est l'auteur, et n'a ni URL ni auteurs tiers.

`platform` et `content_type` deviennent donc nullables : ils decrivent le
contenu documente, et une fiche sujet n'en documente aucun. Les mettre a
`other` aurait garde la meme confusion sous un autre nom.

Backfill : une fiche sans `content_url` ne documente aucun contenu, quelle
qu'ait ete l'intention. C'est la seule regle qui ne se trompe pas sur les
donnees existantes.

Revision ID: 050_card_kind
Revises: 049_agent_session_agent_slug
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "050_card_kind"
down_revision: str | None = "049_agent_session_agent_slug"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column("card_kind", sa.String(20), nullable=False, server_default="contenu"),
    )
    op.alter_column("biblio_cards", "platform", existing_type=sa.String(50), nullable=True)
    op.alter_column("biblio_cards", "content_type", existing_type=sa.String(50), nullable=True)

    op.execute(
        "UPDATE biblio_cards SET card_kind = 'sujet' "
        "WHERE content_url IS NULL OR trim(content_url) = ''"
    )
    # Une fiche sujet ne documente aucun contenu : les colonnes qui le
    # decrivaient ne veulent plus rien dire pour elle.
    op.execute(
        "UPDATE biblio_cards SET platform = NULL, content_type = NULL, "
        "content_authors = NULL WHERE card_kind = 'sujet'"
    )


def downgrade() -> None:
    op.execute("UPDATE biblio_cards SET platform = 'other' WHERE platform IS NULL")
    op.execute("UPDATE biblio_cards SET content_type = 'other' WHERE content_type IS NULL")
    op.alter_column("biblio_cards", "content_type", existing_type=sa.String(50), nullable=False)
    op.alter_column("biblio_cards", "platform", existing_type=sa.String(50), nullable=False)
    op.drop_column("biblio_cards", "card_kind")
