"""Agent nomme attache a une session de chat.

Le slug pointe vers un fichier `agents/<slug>.yaml` du workspace du createur.
NULL = assistant generaliste (tous les outils, tout `shared/`), soit le
comportement d'avant cette colonne.

Pas de cle etrangere : la definition vit dans le workspace, pas en base, et
un slug qui pointe vers un fichier supprime doit degrader vers le
generaliste plutot que casser la session.

Revision ID: 049_agent_session_agent_slug
Revises: 048_ws_style_redactionnel
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "049_agent_session_agent_slug"
down_revision: str | None = "048_ws_style_redactionnel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_sessions", sa.Column("agent_slug", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_sessions", "agent_slug")
