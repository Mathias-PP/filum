"""Mode gratuit : lanes de rotation, usage/cooldown et consentements.

Trois tables :
- agent_lanes : les couples (fournisseur, modele) serveur. La cle API n'y
  figure JAMAIS (elle vient des settings) ; une lane sans cle est ignoree.
- agent_lane_usage : compteur quotidien + cooldown 429 par lane.
- agent_gratuit_consents : consentement versionne par createur.

Seed : la lane Z.ai (GLM, tier gratuit ~1000 req/jour, OpenAI-compatible).
Desactivee par defaut au niveau instance (agent_gratuit_enabled=False).

Revision ID: 050_mode_gratuit
Revises: 049_agent_session_agent_slug
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "050_mode_gratuit"
down_revision: str | None = "049_agent_session_agent_slug"
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
    op.execute(
        sa.text(
            "INSERT INTO agent_lanes "
            "(id, slug, label_public, provider_kind, base_url, model, rpm_cap, rpd_cap, actif, position) "
            "VALUES (:id, 'zai', 'GLM · Z.ai', 'custom', "
            "'https://api.z.ai/api/paas/v4', 'glm-5.2', 3, 900, true, 0)"
        ).bindparams(id=str(uuid.uuid4()))
    )


def downgrade() -> None:
    op.drop_table("agent_gratuit_consents")
    op.drop_index("ix_agent_lane_usage_lane_id", table_name="agent_lane_usage")
    op.drop_table("agent_lane_usage")
    op.drop_index("ix_agent_lanes_slug", table_name="agent_lanes")
    op.drop_table("agent_lanes")
