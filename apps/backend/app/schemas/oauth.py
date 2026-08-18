"""Schemas Pydantic pour les endpoints OAuth 2.1."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClientRegistrationRequest(BaseModel):
    """DCR request (RFC 7591 § 2)."""

    redirect_uris: list[str] = Field(..., min_length=1)
    client_name: str | None = Field(default=None, max_length=200)
    # « none » pour les clients publics (Claude Code, Cursor, ChatGPT :
    # tournent sur la machine de l'user, donc PKCE remplace le secret).
    # « client_secret_basic » pour un client confidentiel (rare).
    token_endpoint_auth_method: str = Field(
        default="none", pattern=r"^(none|client_secret_basic|client_secret_post)$"
    )


class ClientRegistrationResponse(BaseModel):
    """DCR response (RFC 7591 § 3.2.1)."""

    client_id: str
    client_id_issued_at: int
    redirect_uris: list[str]
    grant_types: list[str]
    token_endpoint_auth_method: str
    client_name: str | None = None
    client_secret: str | None = None  # seulement si le client est confidentiel


class TokenResponse(BaseModel):
    """OAuth 2.0 token response (RFC 6749 § 5.1)."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str | None = None
