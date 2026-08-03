"""Ajoute les auteurs du contenu documente sur la fiche.

Revision ID: 018_card_authors
Revises: 017_link_by_content
Create Date: 2026-08-03

Une fiche ne portait aucune trace des auteurs du contenu qu'elle documente.
Le meta-graphe les reconstituait en remontant la bibliographie des fiches
citantes (`Source.authors` de la source qui la designe), ce qui ne marche que
si quelqu'un cite la fiche : sinon le noeud ne pouvait afficher que le nom du
createur Philum, laissant croire qu'il etait l'auteur de l'article ou de la
video decrits.

La colonne materialise l'information sur la fiche elle-meme. Le backfill
applique la regle de reconstitution existante aux donnees deja en base : la
liste d'auteurs la plus complete parmi les sources qui designent la fiche
gagne, la plus ancienne departageant a longueur egale pour rester
deterministe. Les fiches que personne ne cite restent a NULL -- il n'y a rien
a inventer -- et seront renseignees a la prochaine extraction ou a la main.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "018_card_authors"
down_revision: str | None = "017_link_by_content"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column("content_authors", sa.String(length=500), nullable=True),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT linked_card_id, authors
            FROM sources
            WHERE linked_card_id IS NOT NULL
              AND authors IS NOT NULL
              AND btrim(authors) <> ''
              AND deleted_at IS NULL
            ORDER BY created_at
            """
        )
    ).all()

    best: dict[str, str] = {}
    for card_id, authors in rows:
        candidate = authors.strip()[:500]
        current = best.get(str(card_id))
        if current is None or len(candidate) > len(current):
            best[str(card_id)] = candidate

    for card_id, authors in best.items():
        conn.execute(
            sa.text(
                "UPDATE biblio_cards SET content_authors = :a "
                "WHERE id = CAST(:c AS uuid) AND content_authors IS NULL"
            ),
            {"a": authors, "c": card_id},
        )


def downgrade() -> None:
    op.drop_column("biblio_cards", "content_authors")
