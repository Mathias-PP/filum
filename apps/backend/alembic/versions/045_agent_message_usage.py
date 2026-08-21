"""Ajoute prompt_tokens et completion_tokens sur agent_messages.

Permet de comptabiliser l'usage token par tour et d'agréger le coût
d'une session entière via GET /agent/sessions/{id}/usage.

Revision ID: 045_agent_message_usage
Revises: 044_normalize_enum_sources
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "045_agent_message_usage"
down_revision: str | None = "044_normalize_enum_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_messages",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "completion_tokens")
    op.drop_column("agent_messages", "prompt_tokens")
