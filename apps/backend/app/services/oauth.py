"""Logique OAuth 2.1 pour l'auth MCP.

L'architecture volontairement mince : les access tokens sont des JWT signes
avec la meme cle que les sessions Philum (aucune table, verifies a la volee),
seul le flow d'autorisation (client register + code) touche la base.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.oauth import OAuthAuthorizationCode, OAuthClient
from app.services.auth import ALGORITHM

settings = get_settings()

#: 24h : plus long que la duree d'une session de travail humain, plus court
#: qu'un mois. Sans refresh token, l'user re-autorise chaque jour. Suffisant
#: en V1 ; un refresh token pourra rallonger sans casser la compatibilite.
ACCESS_TOKEN_EXPIRE_HOURS = 24

#: 5 minutes : recommandation RFC 6749 § 4.1.2 (< 10 min). Un code expire vite
#: parce qu'il est presque toujours echange dans les secondes qui suivent son
#: emission. Plus la fenetre est courte, moins un code fuite (referer, logs,
#: historique navigateur) est reutilisable.
AUTH_CODE_EXPIRE_MINUTES = 5


def _b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _random_token(nbytes: int = 32) -> str:
    return _b64url_no_pad(secrets.token_bytes(nbytes))


def hash_secret(secret: str) -> str:
    """SHA-256 hex. Suffisant pour un secret aleatoire de 256 bits (pas de
    bcrypt : le secret n'est pas un mot de passe humain, il n'y a rien a
    resister a un dictionnaire)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verifie la PKCE (RFC 7636). Seul S256 est accepte (OAuth 2.1 refuse plain).

    Le code_verifier est envoye par le client au /token endpoint. On calcule
    S256(verifier) et on compare au challenge stocke au /authorize endpoint.
    """
    if method != "S256":
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = _b64url_no_pad(digest)
    # Comparaison timing-safe : evite de fuir la longueur du prefix commun.
    return secrets.compare_digest(expected, code_challenge)


async def register_client(
    db: AsyncSession,
    *,
    redirect_uris: list[str],
    client_name: str | None = None,
    token_endpoint_auth_method: str = "none",
) -> dict[str, Any]:
    """Enregistre un client MCP (RFC 7591 Dynamic Client Registration).

    `token_endpoint_auth_method='none'` = client public (PKCE remplace le
    secret). C'est ce que font Claude Code, Cursor, ChatGPT desktop : ils
    tournent sur la machine de l'utilisateur, donc un secret ne serait pas
    vraiment secret. La PKCE prouve la possession du code sans secret partage.

    Retourne le format standard RFC 7591 § 3.2.1.
    """
    if not redirect_uris:
        raise ValueError("redirect_uris ne peut pas etre vide")
    for uri in redirect_uris:
        if not (
            uri.startswith("http://localhost")
            or uri.startswith("https://")
            or uri.startswith("http://127.0.0.1")
        ):
            raise ValueError(
                f"redirect_uri {uri!r} refuse : seules https:// et loopback http://localhost/127.0.0.1 sont acceptees"
            )

    client_id = _random_token(24)
    client_secret: str | None = None
    client_secret_hash: str | None = None
    if token_endpoint_auth_method != "none":  # nosec B105 - valeur OAuth, pas un mot de passe
        client_secret = _random_token(32)
        client_secret_hash = hash_secret(client_secret)

    client = OAuthClient(
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        client_name=client_name,
        redirect_uris=redirect_uris,
        grant_types=["authorization_code"],
        token_endpoint_auth_method=token_endpoint_auth_method,
    )
    db.add(client)
    await db.commit()

    resp: dict[str, Any] = {
        "client_id": client_id,
        "client_id_issued_at": int(datetime.now(UTC).timestamp()),
        "redirect_uris": redirect_uris,
        "grant_types": ["authorization_code"],
        "token_endpoint_auth_method": token_endpoint_auth_method,
    }
    if client_name:
        resp["client_name"] = client_name
    if client_secret:
        resp["client_secret"] = client_secret
    return resp


async def get_client(db: AsyncSession, client_id: str) -> OAuthClient | None:
    result = await db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    return result


async def create_authorization_code(
    db: AsyncSession,
    *,
    client: OAuthClient,
    user_id: UUID,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str | None = None,
) -> str:
    """Cree un code d'autorisation apres consentement utilisateur.

    Refuse si `redirect_uri` n'est pas dans la liste blanche du client, ou si
    la methode PKCE n'est pas S256.
    """
    if redirect_uri not in client.redirect_uris:
        raise ValueError(f"redirect_uri {redirect_uri!r} non autorisee pour ce client")
    if code_challenge_method != "S256":
        raise ValueError("code_challenge_method doit etre S256 (OAuth 2.1)")

    code = _random_token(32)
    entry = OAuthAuthorizationCode(
        code=code,
        client_id=client.client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=scope,
        expires_at=datetime.now(UTC).replace(tzinfo=None)
        + timedelta(minutes=AUTH_CODE_EXPIRE_MINUTES),
    )
    db.add(entry)
    await db.commit()
    return code


async def exchange_code_for_token(
    db: AsyncSession,
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Echange un code d'autorisation contre un access token JWT.

    Verifie : code existe, appartient au bon client, meme redirect_uri qu'au
    /authorize, PKCE valide, code non expire, code non deja utilise. Marque
    le code comme utilise (SET used_at) avant de rendre le token.
    """
    entry = await db.scalar(
        select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code == code)
    )
    if entry is None:
        raise ValueError("invalid_grant: code inconnu")
    if entry.client_id != client_id:
        raise ValueError("invalid_grant: code emis pour un autre client")
    if entry.redirect_uri != redirect_uri:
        raise ValueError("invalid_grant: redirect_uri ne correspond pas")
    if entry.used_at is not None:
        raise ValueError("invalid_grant: code deja utilise")
    if entry.expires_at < datetime.now(UTC).replace(tzinfo=None):
        raise ValueError("invalid_grant: code expire")
    if not verify_pkce(code_verifier, entry.code_challenge, entry.code_challenge_method):
        raise ValueError("invalid_grant: code_verifier invalide")

    entry.used_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    now = datetime.now(UTC)
    expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(entry.user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        # Marque l'origine du token pour audit. `app/mcp_server/auth.py` doit
        # decoder avec `verify_aud=False` : PyJWT rejette un token porteur
        # d'`aud` quand l'appelant n'en annonce aucune.
        "aud": "mcp",
        "client_id": client_id,
    }
    access_token = jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)

    return {
        "access_token": access_token,
        "token_type": "Bearer",  # nosec B105 - type OAuth (RFC 6749), pas un mot de passe
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "scope": entry.scope,
    }
