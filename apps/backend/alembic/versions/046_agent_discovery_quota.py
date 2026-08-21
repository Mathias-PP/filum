"""Table de quota quotidien pour le mode decouverte (A11).

Chaque ligne compte les messages consommes par un createur un jour donne
en mode decouverte (cle sponsorisee Philum). Une contrainte UNIQUE empeche
deux lignes pour le meme creator_id + date.

Revision ID: 046_agent_discovery_quota
Revises: 045_agent_message_usage
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "046_agent_discovery_quota"
down_revision: str | None = "045_agent_message_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_discovery_quota",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("creator_id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("messages_used", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "date", name="uq_discovery_quota_creator_date"),
    )
    op.create_index(
        "ix_agent_discovery_quota_creator_id",
        "agent_discovery_quota",
        ["creator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_discovery_quota_creator_id", table_name="agent_discovery_quota")
    op.drop_table("agent_discovery_quota")
