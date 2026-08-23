"""Mode gratuit : lanes de rotation, usage/cooldown et consentements.

Trois tables :
- agent_lanes : les couples (fournisseur, modele) serveur. La cle API n'y
  figure JAMAIS (elle vient des settings) ; une lane sans cle est ignoree.
- agent_lane_usage : compteur quotidien + cooldown 429 par lane.
- agent_gratuit_consents : consentement versionne par createur.

Seed : la lane Z.ai (GLM, tier gratuit ~1000 req/jour, OpenAI-compatible).
Desactivee par defaut au niveau instance (agent_gratuit_enabled=False).

Cette revision est nee en parallele de `050_card_kind`, sur une branche partie
du meme parent, et les deux ont ete mergees le meme jour : Alembic s'est
retrouve avec deux tetes, `upgrade head` a refuse de choisir, et le conteneur a
redemarre en boucle. Elle est replacee derriere `050_card_kind` plutot que
rejointe par une revision de jonction, qui aurait rendu `downgrade -1` ambigu
pour toujours. Les deux migrations touchent des tables disjointes : les
ordonner ne change rien.

Revision ID: 051_mode_gratuit
Revises: 050_card_kind
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "051_mode_gratuit"
down_revision: str | None = "050_card_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_lanes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("label_public", sa.String(80), nullable=False),
        sa.Column("provider_kind", sa.String(30), nullable=False, server_default="custom"),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("rpm_cap", sa.Integer(), nullable=True),
        sa.Column("rpd_cap", sa.Integer(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_lanes_slug", "agent_lanes", ["slug"], unique=True)

    op.create_table(
        "agent_lane_usage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lane_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lane_id", "date", name="uq_agent_lane_usage_lane_date"),
    )
    op.create_index("ix_agent_lane_usage_lane_id", "agent_lane_usage", ["lane_id"])

    op.create_table(
        "agent_gratuit_consents",
        sa.Column("creator_id", sa.String(64), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("consent_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("creator_id"),
    )

    # Lane Z.ai : GLM en tier gratuit (~1000 req/jour), endpoint OpenAI-
    # compatible. rpd_cap volontairement sous le plafond reel pour garder une
    # marge ; la cle vient de AGENT_GRATUIT_ZAI_API_KEY.
    #
    # `bulk_insert` et pas un INSERT en texte : PostgreSQL refuse une chaine
    # dans une colonne `uuid`, la ou SQLite l'accepte. Declarer les types laisse
    # SQLAlchemy adapter la valeur au dialecte, et la migration passe des deux
    # cotes.
    op.bulk_insert(
        sa.table(
            "agent_lanes",
            sa.column("id", sa.Uuid()),
            sa.column("slug", sa.String),
            sa.column("label_public", sa.String),
            sa.column("provider_kind", sa.String),
            sa.column("base_url", sa.String),
            sa.column("model", sa.String),
            sa.column("rpm_cap", sa.Integer),
            sa.column("rpd_cap", sa.Integer),
            sa.column("actif", sa.Boolean),
            sa.column("position", sa.Integer),
        ),
        [
            {
                "id": uuid.uuid4(),
                "slug": "zai",
                "label_public": "GLM · Z.ai",
                "provider_kind": "custom",
                "base_url": "https://api.z.ai/api/paas/v4",
                "model": "glm-5.2",
                "rpm_cap": 3,
                "rpd_cap": 900,
                "actif": True,
                "position": 0,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("agent_gratuit_consents")
    op.drop_index("ix_agent_lane_usage_lane_id", table_name="agent_lane_usage")
    op.drop_table("agent_lane_usage")
    op.drop_index("ix_agent_lanes_slug", table_name="agent_lanes")
    op.drop_table("agent_lanes")
