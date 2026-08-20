"""Table des providers IA BYOK des créateurs.

Chaque créateur enregistre ses comptes IA (OpenAI, Anthropic, DeepSeek, Gemini —
ou tout endpoint OpenAI-compatible en mode custom), désigne un défaut et teste
sa clé. La clé API est chiffrée AES-GCM via le `master_encryption_key` existant
(jamais en clair en base) ; seule la colonne `api_key_enc` la porte.

`base_url` est NOT NULL même pour les providers intégrés : la valeur par défaut
du provider est résolue à la création. Ainsi l'unicité
`(creator_id, provider, base_url, model)` reste exploitable sans le piège des
NULL distincts dans les contraintes uniques PostgreSQL.

Un seul `is_default` par créateur : c'est une contrainte applicative (le service
efface les autres avant d'en poser un), pas une contrainte partielle SQL.

Revision ID: 040_agent_providers
Revises: 039_oauth_dcr
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "040_agent_providers"
down_revision: str | None = "039_oauth_dcr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Le créateur propriétaire de ce compte IA. CASCADE : supprimer le compte efface ses clés.",
        ),
        sa.Column(
            "provider",
            sa.String(20),
            nullable=False,
            comment="openai | anthropic | deepseek | gemini | custom",
        ),
        sa.Column(
            "display_name",
            sa.String(80),
            nullable=False,
            comment="Nom lisible affiché dans l'UI. Défaut = provider ; personnalisable.",
        ),
        sa.Column(
            "base_url",
            sa.String(300),
            nullable=False,
            comment="Racine de l'API. Résolue au défaut du provider à la création.",
        ),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column(
            "api_key_enc",
            sa.Text(),
            nullable=False,
            comment="Clé API chiffrée AES-GCM, base64(nonce + ciphertext). Jamais en clair.",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Un seul défaut par créateur (contrainte applicative).",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "creator_id",
            "provider",
            "base_url",
            "model",
            name="uq_agent_providers_creator_provider_url_model",
        ),
    )
    op.create_index("ix_agent_providers_creator_id", "agent_providers", ["creator_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_providers_creator_id", table_name="agent_providers")
    op.drop_table("agent_providers")
