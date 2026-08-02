"""Rattache les sources aux fiches qui documentent le meme contenu.

Revision ID: 017_link_by_content
Revises: 016_merge_parent_card
Create Date: 2026-08-02

Jusqu'ici `linked_card_id` n'etait rempli que si quelqu'un avait choisi la
fiche au picker, ou colle une URL Philum. Une reference vers un article et la
fiche Philum qui documente cet article restaient donc deux objets sans lien :
sur le meta-graphe la meme reference apparaissait deux fois, une fois comme
fiche depliable, une fois comme source isolee.

Le code resout desormais ce lien par identite de contenu (meme DOI, ou meme
URL normalisee). Cette migration applique la meme regle aux donnees deja en
base. Elle est idempotente : elle ne touche que les sources sans lien.

Elle reutilise `app.services.content_identity` plutot que d'en recopier la
normalisation. Ce module est pur et sans dependance ; le couplage est assume.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.services.content_identity import escape_like, extract_doi, url_variants

revision: str = "017_link_by_content"
down_revision: str | None = "016_merge_parent_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    cards = conn.execute(
        sa.text(
            "SELECT id, content_url FROM biblio_cards "
            "WHERE content_url IS NOT NULL AND status = 'published' "
            "AND visibility = 'public' AND deleted_at IS NULL "
            "ORDER BY created_at"
        )
    ).fetchall()

    for card_id, content_url in cards:
        clauses: list[str] = []
        params: dict[str, object] = {"cid": card_id}
        variants = url_variants(content_url)
        if variants:
            clauses.append("url IN :variants")
            params["variants"] = tuple(variants)
        doi = extract_doi(content_url)
        if doi:
            params["doi"] = f"%{escape_like(doi)}%"
            clauses.append(r"(doi ILIKE :doi ESCAPE '\' OR url ILIKE :doi ESCAPE '\')")
        if not clauses:
            continue

        stmt = sa.text(
            "UPDATE sources SET linked_card_id = :cid "
            "WHERE linked_card_id IS NULL AND deleted_at IS NULL "
            "AND biblio_card_id <> :cid "
            f"AND ({' OR '.join(clauses)})"
        )
        if variants:
            stmt = stmt.bindparams(sa.bindparam("variants", expanding=True))
        conn.execute(stmt, params)


def downgrade() -> None:
    # Les liens poses ici sont indiscernables de ceux poses au picker : les
    # retirer effacerait du travail utilisateur. On ne defait rien.
    pass
