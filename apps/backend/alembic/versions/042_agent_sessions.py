"""Sessions de chat de l'agent et leurs messages.

Sans ces deux tables, le moteur livré en Phase 3 repart de zéro à chaque
échange : le client renvoyait son propre historique, donc l'agent n'avait
aucune mémoire que l'utilisateur ne lui redonnait pas, et rien ne survivait
à un rechargement de page.

`agent_messages` est **append-only** : un tour d'agent est une trace, pas un
document. On n'y fait jamais d'UPDATE, sans quoi l'historique cesserait de
dire ce que le modèle a réellement vu quand il a décidé.

Revision ID: 042_agent_sessions
Revises: 041_workspace_files
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "042_agent_sessions"
down_revision: str | None = "041_workspace_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Créateur propriétaire. CASCADE : supprimer le compte efface ses conversations.",
        ),
        sa.Column(
            "title",
            sa.String(200),
            nullable=False,
            server_default="",
            comment="Titre lisible, derivé du premier message si l'utilisateur n'en donne pas.",
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_providers.id", ondelete="SET NULL"),
            nullable=True,
            comment="Provider utilisé. SET NULL : retirer une clé ne doit pas effacer l'historique.",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
            comment="Suppression logique : la trace reste, la session sort des listes.",
        ),
    )
    op.create_index("ix_agent_sessions_creator_id", "agent_sessions", ["creator_id"])

    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            comment="user | assistant | tool | system",
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Outils demandés par le modèle sur ce message, tels que rendus par le provider.",
        ),
        sa.Column(
            "tool_name",
            sa.String(80),
            nullable=True,
            comment="Nom de l'outil pour un message de rôle `tool`.",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_messages_session_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_creator_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
