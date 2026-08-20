"""Table des fichiers du workspace ICM hébergé d'un créateur.

Chaque créateur a une copie persistée en base du template ICM
(`app/agent_workspace_seed/`) : AGENTS.md, CONTEXT.md, `shared/`, `stages/`,
`_core/`. Le chemin est normalisé (relatif, racines fermées) par le service
avant toute écriture ; `sha256` traçe le contenu pour l'audit de l'agent.

L'isolation multi-tenant est applicative (le service scope par `creator_id`) ;
PostgreSQL est déjà en RLS-enable sur les tables public (cf. `030_rls_lockdown`),
mais le backend se connecte avec `BYPASSRLS` : la vraie garde est l'applicatif.

Revision ID: 041_workspace_files
Revises: 040_agent_providers
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "041_workspace_files"
down_revision: str | None = "040_agent_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Créateur propriétaire du fichier. CASCADE : supprimer le compte efface son workspace.",
        ),
        sa.Column(
            "path",
            sa.String(500),
            nullable=False,
            comment="Chemin normalisé relatif (racines fermées : shared/, stages/, _core/, runs/, setup/, agents/).",
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default="", comment="Contenu du fichier"),
        sa.Column(
            "sha256",
            sa.String(64),
            nullable=False,
            comment="Hash SHA-256 hex du contenu (traçabilité pour l'audit de l'agent).",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("creator_id", "path", name="uq_workspace_files_creator_path"),
    )
    op.create_index("ix_workspace_files_creator_id", "workspace_files", ["creator_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_files_creator_id", table_name="workspace_files")
    op.drop_table("workspace_files")