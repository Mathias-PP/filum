"""Modeles OAuth 2.1 pour l'auth MCP standard.

Deux tables courtes : un registre des clients qui se sont enregistres via
DCR (RFC 7591), et une table de codes d'autorisation ephemeres qui bridgent
la page de consentement (`/oauth/authorize`) et l'obtention du token
(`/oauth/token`).

Pas de table pour les access tokens : ils sont des JWT signes avec la meme
cle que les sessions Philum, verifies a la volee par le middleware MCP
existant. Zero I/O par requete authentifiee.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

#: JSONB en PostgreSQL (indexable, typé), JSON portable partout ailleurs
#: (SQLite en tests). Sans ce with_variant, SQLite plante au create_all.
_JSON_LIST = JSON().with_variant(JSONB(), "postgresql")


class OAuthClient(Base):
    """Un client MCP enregistre via DCR.

    `client_id` est genere aleatoirement au moment de l'enregistrement et
    reste stable pour la vie du client. `client_secret_hash` est NULL pour
    les clients publics (Claude Code, Cursor : PKCE remplace le secret) et
    stocke un hash SHA-256 pour les clients confidentiels (backend a backend).
    """

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    redirect_uris: Mapped[list[str]] = mapped_column(_JSON_LIST, nullable=False)
    grant_types: Mapped[list[str]] = mapped_column(_JSON_LIST, nullable=False)
    token_endpoint_auth_method: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class OAuthAuthorizationCode(Base):
    """Un code d'autorisation en attente d'echange contre un access token.

    Duree de vie 5 minutes, usage unique (`used_at`). La PKCE (`code_challenge`
    + `code_challenge_method`) prouve au token endpoint que le porteur du code
    est bien celui qui a lance le flow : sans elle, un attaquant qui capture
    l'URL de callback (via logs, historique navigateur, referer) pourrait
    echanger le code.
    """

    __tablename__ = "oauth_authorization_codes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
