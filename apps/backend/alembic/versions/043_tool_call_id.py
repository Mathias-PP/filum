"""Ajoute ``tool_call_id`` sur ``agent_messages``.

Sans cet identifiant sur les messages de rôle ``tool``, Gemini rejette la
requête suivante avec HTTP 400 INVALID_ARGUMENT (spec OpenAI que Gemini
applique strictement). OpenAI est tolérant, ce qui a masqué le bug jusqu'à la
première conversation lancée sur Gemini en prod le 2026-08-21. Nullable : les
lignes existantes ne peuvent pas être reconstruites et rejoueront sans id sur
Gemini (comportement dégradé, pas un crash).

Revision ID: 043_tool_call_id
Revises: 042_agent_sessions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "043_tool_call_id"
down_revision: str | None = "042_agent_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("tool_call_id", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "tool_call_id")
