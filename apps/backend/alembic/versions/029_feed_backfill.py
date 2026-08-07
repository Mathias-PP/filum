"""Backfill du feed : inscrire les fiches publiques deja publiees.

La migration 028 a cree la table `feed_events` mais elle est vide. Sans
backfill, le feed public commence a se remplir a la prochaine publication
et donne l'impression d'un site desert. Ce backfill inscrit toutes les
fiches deja publiquement publiees, en utilisant leur `published_at` comme
`occurred_at` : c'est la date reelle a laquelle elles sont apparues.

Idempotent : la sous-requete NOT EXISTS empeche un double-run de creer
des doublons, meme si la migration devait etre rejouee.

Revision ID: 029_feed_backfl
Revises: 028_feed_events
"""

from __future__ import annotations

from alembic import op

revision: str = "029_feed_backfl"
down_revision: str | None = "028_feed_events"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO feed_events (id, kind, actor_id, card_id, occurred_at)
        SELECT
            gen_random_uuid(),
            'card_published',
            c.user_id,
            c.id,
            c.published_at
        FROM biblio_cards c
        WHERE c.status = 'published'
          AND c.visibility = 'public'
          AND c.deleted_at IS NULL
          AND c.published_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM feed_events fe
              WHERE fe.card_id = c.id AND fe.kind = 'card_published'
          )
        """
    )


def downgrade() -> None:
    # On ne supprime pas les entrees inserees : elles sont indistinguables des
    # entrees creees par publish_card apres la migration. La table entiere
    # sera droppee par le downgrade de 028_feed_events si besoin.
    pass
