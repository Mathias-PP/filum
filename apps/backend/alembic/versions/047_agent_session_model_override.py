"""Override de modele par session de chat.

Permet de choisir un modele different du provider par defaut pour une
session sans muter le provider global. NULL = utiliser provider.model.

Revision ID: 047_agent_session_model_override
Revises: 046_agent_discovery_quota
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "047_agent_session_model_override"
down_revision: str | None = "046_agent_discovery_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column("model_override", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_sessions", "model_override")
