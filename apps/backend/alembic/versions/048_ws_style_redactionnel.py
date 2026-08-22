"""Renomme `shared/voix-createur.md` en `shared/style-redactionnel.md`.

Le seed n'insere que les chemins absents : sans ce renommage, un createur
qui possede deja l'ancien fichier se retrouverait avec les deux, et ses
modifications resteraient dans celui que plus aucun contexte ne cite.

Un createur qui possede deja les deux (cas theorique) garde le nouveau :
la mise a jour est filtree pour ne pas violer `uq_workspace_files_creator_path`.

Revision ID: 048_workspace_rename_style_redactionnel
Revises: 047_agent_session_model_override
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "048_workspace_rename_style_redactionnel"
down_revision: str | None = "047_agent_session_model_override"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANCIEN = "shared/voix-createur.md"
_NOUVEAU = "shared/style-redactionnel.md"


def _renommer(source: str, cible: str) -> None:
    op.execute(
        f"""
        UPDATE workspace_files AS f
        SET path = '{cible}'
        WHERE f.path = '{source}'
          AND NOT EXISTS (
            SELECT 1 FROM workspace_files AS autre
            WHERE autre.creator_id = f.creator_id AND autre.path = '{cible}'
          )
        """
    )
    op.execute(f"DELETE FROM workspace_files WHERE path = '{source}'")


def upgrade() -> None:
    _renommer(_ANCIEN, _NOUVEAU)


def downgrade() -> None:
    _renommer(_NOUVEAU, _ANCIEN)
