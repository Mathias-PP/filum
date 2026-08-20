"""Le flow OAuth 2.1 complet, du DCR au JWT.

Ces tests couvrent le chemin qu'un client MCP (Claude Code, Cursor,
ChatGPT desktop, Zed...) fait automatiquement quand un utilisateur ajoute
`https://philum-api.duckdns.org/mcp/` dans son client :

1. Fetch `/.well-known/oauth-authorization-server` pour decouvrir les
   endpoints.
2. `POST /oauth/register` pour se declarer avec un `redirect_uri` local
   (ex : `http://localhost:14567/callback`).
3. Ouvre le navigateur sur `/oauth/authorize?...&code_challenge=...`.
4. L'utilisateur clique « Autoriser » sur la page consent, le serveur
   redirige vers le callback avec `?code=...`.
5. `POST /oauth/token` avec le `code_verifier` pour recuperer l'access
   token.

L'utilisateur n'a jamais rien colle a la main.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def _b64url_no_pad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _pkce_pair() -> tuple[str, str]:
    """(verifier, challenge_S256) pour un test PKCE valide."""
    verifier = _b64url_no_pad(secrets.token_bytes(32))
    challenge = _b64url_no_pad(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_metadata_serveur_expose_les_endpoints(client):
    """Un client MCP fetch ce document pour tout decouvrir."""
    r = await client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    data = r.json()
    assert data["authorization_endpoint"].endswith("/api/v1/oauth/authorize")
    assert data["token_endpoint"].endswith("/api/v1/oauth/token")
    assert data["registration_endpoint"].endswith("/api/v1/oauth/register")
    assert "S256" in data["code_challenge_methods_supported"]
    assert "authorization_code" in data["grant_types_supported"]


@pytest.mark.asyncio
async def test_protected_resource_metadata_pointe_vers_l_as(client):
    """RFC 9728 : ce que le client MCP lit apres avoir vu un 401 sur /mcp-account/.

    Le document par defaut decrit la porte qui exige une authentification.
    La porte publique a son propre document sous /mcp-account.
    """
    r = await client.get("/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    data = r.json()
    assert data["resource"].endswith("/mcp-account/")
    assert len(data["authorization_servers"]) == 1
    assert data["bearer_methods_supported"] == ["header"]

    # La porte publique a son propre document.
    r2 = await client.get("/.well-known/oauth-protected-resource/mcp")
    assert r2.status_code == 200
    assert r2.json()["resource"].endswith("/mcp/")


@pytest.mark.asyncio
async def test_register_puis_authorize_puis_token_donne_un_jwt(client, test_user, db_session):
    """Le flow complet, tel qu'un client MCP l'execute automatiquement."""
    # 1. DCR : le client se declare
    r = await client.post(
        "/api/v1/oauth/register",
        json={
            "redirect_uris": ["http://localhost:14567/callback"],
            "client_name": "Test MCP Client",
            "token_endpoint_auth_method": "none",
        },
    )
    assert r.status_code == 201, r.text
    client_data = r.json()
    client_id = client_data["client_id"]
    assert client_data["token_endpoint_auth_method"] == "none"
    assert client_data.get("client_secret") is None  # client public, pas de secret

    # 2. authorize : simule le clic « Autoriser » de l'user via POST consent.
    #    L'user est deja logue (via override get_current_user).
    verifier, challenge = _pkce_pair()

    from app.api.v1.endpoints.auth import get_current_user
    from app.main import app

    async def override_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_user

    r = await client.post(
        "/api/v1/oauth/consent",
        data={
            "decision": "allow",
            "client_id": client_id,
            "redirect_uri": "http://localhost:14567/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "opaque-state-42",
        },
        follow_redirects=False,
    )
    # 302 vers le callback avec code=... et state=opaque-state-42
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith("http://localhost:14567/callback?")
    assert "code=" in location
    assert "state=opaque-state-42" in location
    # Extraction du code
    code = location.split("code=")[1].split("&")[0]

    # 3. token : echange contre un JWT
    r = await client.post(
        "/api/v1/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:14567/callback",
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert r.status_code == 200, r.text
    token_data = r.json()
    assert token_data["token_type"] == "Bearer"
    assert token_data["expires_in"] > 0

    # Le JWT contient bien l'user
    from app.core.config import get_settings
    from app.services.auth import ALGORITHM

    decoded = jwt.decode(
        token_data["access_token"],
        get_settings().session_secret,
        algorithms=[ALGORITHM],
        audience="mcp",
    )
    assert decoded["sub"] == str(test_user.id)
    assert decoded["aud"] == "mcp"
    assert decoded["client_id"] == client_id


@pytest.mark.asyncio
async def test_refuse_pkce_plain_car_oauth_2_1_impose_s256(client):
    r = await client.post(
        "/api/v1/oauth/register",
        json={"redirect_uris": ["http://localhost:1234/cb"]},
    )
    client_id = r.json()["client_id"]

    r = await client.get(
        "/api/v1/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "http://localhost:1234/cb",
            "code_challenge": "test",
            "code_challenge_method": "plain",  # refuse
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_refuse_redirect_uri_non_enregistree(client):
    r = await client.post(
        "/api/v1/oauth/register",
        json={"redirect_uris": ["http://localhost:1234/cb"]},
    )
    client_id = r.json()["client_id"]
    r = await client.get(
        "/api/v1/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "http://evil.example/cb",  # pas enregistree
            "code_challenge": "aaa",
            "code_challenge_method": "S256",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_code_echangeable_une_seule_fois(client, test_user):
    """Un code deja utilise est refuse au second echange (defense en profondeur)."""
    from app.api.v1.endpoints.auth import get_current_user
    from app.main import app

    async def override_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_user

    r = await client.post(
        "/api/v1/oauth/register",
        json={"redirect_uris": ["http://localhost:9000/cb"]},
    )
    client_id = r.json()["client_id"]
    verifier, challenge = _pkce_pair()

    r = await client.post(
        "/api/v1/oauth/consent",
        data={
            "decision": "allow",
            "client_id": client_id,
            "redirect_uri": "http://localhost:9000/cb",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    code = r.headers["location"].split("code=")[1].split("&")[0]

    # Premier echange : OK
    r = await client.post(
        "/api/v1/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:9000/cb",
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert r.status_code == 200

    # Deuxieme echange avec le meme code : refuse
    r = await client.post(
        "/api/v1/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:9000/cb",
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert r.status_code == 400
    assert "invalid_grant" in r.text


@pytest.mark.asyncio
async def test_pkce_verifier_invalide_est_refuse(client, test_user):
    from app.api.v1.endpoints.auth import get_current_user
    from app.main import app

    async def override_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_user

    r = await client.post(
        "/api/v1/oauth/register",
        json={"redirect_uris": ["http://localhost:9001/cb"]},
    )
    client_id = r.json()["client_id"]
    _verifier, challenge = _pkce_pair()

    r = await client.post(
        "/api/v1/oauth/consent",
        data={
            "decision": "allow",
            "client_id": client_id,
            "redirect_uri": "http://localhost:9001/cb",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    code = r.headers["location"].split("code=")[1].split("&")[0]

    # Verifier au hasard, ne correspond pas au challenge
    r = await client.post(
        "/api/v1/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:9001/cb",
            "client_id": client_id,
            "code_verifier": "faux_verifier_qui_ne_hash_pas_au_challenge",
        },
    )
    assert r.status_code == 400
    assert "invalid_grant" in r.text


@pytest.mark.asyncio
async def test_mcp_authentification_middleware():
    """La porte /mcp-account repond 401 + WWW-Authenticate quand aucun token n'est fourni.

    Teste le middleware `mcp_authentification` directement sur l'app principale.
    Les tests de comportement plus detailles vivent dans test_mcp_mount.py.
    """
    from fastapi.testclient import TestClient

    from app.main import _mcp_rate_storage, app

    _mcp_rate_storage.reset()
    with TestClient(app) as client:
        r = client.get("/mcp-account/", follow_redirects=False)
        assert r.status_code == 401
        auth = r.headers.get("WWW-Authenticate", "")
        assert "resource_metadata=" in auth
        assert "/.well-known/oauth-protected-resource/mcp-account" in auth
        # La porte publique n'est pas bloquee sans token
        r2 = client.get("/mcp", follow_redirects=False)
        assert r2.status_code != 401
