"""Tables OAuth 2.1 pour l'auth MCP standard.

L'ancien flow (POST /auth/mcp-token depuis DevTools, copier le JWT dans un
fichier de config) exigeait cinq clics et un editeur de texte : hostile aux
utilisateurs, deconseille par la spec MCP depuis mars 2025. Ces tables
supportent OAuth 2.1 avec Dynamic Client Registration (RFC 7591) et PKCE
(RFC 7636), ce qui rend l'ajout d'un serveur MCP a un client (Claude Code,
Cursor, ChatGPT, etc.) une operation en un clic : le client se registre
lui-meme, ouvre une popup navigateur, l'user autorise, terminee.

`oauth_clients` : chaque client MCP se registre une fois puis reutilise son
client_id/client_secret. `redirect_uris` porte la liste blanche des URLs
que le client peut recevoir en callback (voir RFC 7591 § 2).

`oauth_authorization_codes` : codes de courte duree (5 min) qui bridgent le
consentement utilisateur (a l'endpoint /oauth/authorize) et l'obtention du
token (au /oauth/token). `code_challenge` + `code_challenge_method` portent
la PKCE : le client prouve qu'il a genere le code, personne d'autre.

Pas de refresh_token en V1 : access_token dure 24h, l'user re-autorise si
besoin. Suffisant pour un demarrage ; peut etre ajoute plus tard sans
migration disruptive (nouvelle table `oauth_refresh_tokens` autonome).

Revision ID: 039_oauth_dcr
Revises: 038_content_text
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "039_oauth_dcr"
down_revision: str | None = "038_content_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column(
            "client_id",
            sa.String(64),
            primary_key=True,
            comment="Genere en enregistrement (RFC 7591 § 3.2.1). Public.",
        ),
        sa.Column(
            "client_secret_hash",
            sa.String(128),
            nullable=True,
            comment="SHA-256 hex du client_secret. NULL pour clients publics (PKCE only).",
        ),
        sa.Column(
            "client_name",
            sa.String(200),
            nullable=True,
            comment="Nom lisible affiche sur la page consent. Ex : « Claude Code ».",
        ),
        sa.Column(
            "redirect_uris",
            postgresql.JSONB(),
            nullable=False,
            comment="Liste blanche des callback URIs (RFC 7591 § 2). Au moins une.",
        ),
        sa.Column(
            "grant_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"authorization_code\"]'::jsonb"),
        ),
        sa.Column(
            "token_endpoint_auth_method",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'none'"),
            comment="'none' pour PKCE public, 'client_secret_basic' pour confidentiel.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "oauth_authorization_codes",
        sa.Column(
            "code",
            sa.String(64),
            primary_key=True,
            comment="Aleatoire cryptographique. Usage unique : SET used_at des l'echange.",
        ),
        sa.Column(
            "client_id",
            sa.String(64),
            sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column(
            "code_challenge",
            sa.String(128),
            nullable=False,
            comment="PKCE challenge (RFC 7636). Le token endpoint verifie code_verifier contre ca.",
        ),
        sa.Column(
            "code_challenge_method",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'S256'"),
            comment="OAuth 2.1 impose S256 ; on refuse 'plain'.",
        ),
        sa.Column(
            "scope",
            sa.String(500),
            nullable=True,
            comment="Scopes demandes par le client. Non impose dans la V1 (tout access).",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=False),
            nullable=False,
            comment="5 minutes apres creation (RFC 6749 § 4.1.2 recommande <10 min).",
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=False),
            nullable=True,
            comment="Usage unique : un code deja echange est refuse.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_oauth_codes_expires_at",
        "oauth_authorization_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_codes_expires_at", table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
    op.drop_table("oauth_clients")
