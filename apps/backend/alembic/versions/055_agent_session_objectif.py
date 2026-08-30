"""Objectif et phase courante d'une session de chat.

Sur un tour long, l'agent redérive son intention du seul historique, qui est
justement ce que la compaction ampute : au bout de quelques compactions il ne
sait plus ce qu'on lui a demandé au départ. Deux colonnes suffisent à le
retenir hors de l'historique, et le prompt système les réinjecte à chaque tour.

NULL = aucun objectif posé, soit le comportement d'avant ces colonnes.

Revision ID: 055_agent_session_objectif
Revises: 054_graph_trgm
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "055_agent_session_objectif"
down_revision: str | None = "054_graph_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_sessions", sa.Column("objectif", sa.String(400), nullable=True))
    op.add_column("agent_sessions", sa.Column("phase", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_sessions", "phase")
    op.drop_column("agent_sessions", "objectif")
