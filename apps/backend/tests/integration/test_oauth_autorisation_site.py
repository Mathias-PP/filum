"""L'autorisation OAuth d'un client MCP passe par le site, ou vit la session.

Mesure du 2026-09-13 : autoriser Claude Code sur /mcp-account/ echouait en
`invalid_state`. La page d'autorisation etait servie par l'API, qui ne voit pas
la session posee sur le domaine du site ; la connexion Google posait son cookie
d'etat sur l'API et revenait sur le site, ou il n'existait pas. Et le retour de
connexion ignorait `return_to`.
"""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import auth as auth_endpoints
from app.core.config import get_settings


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _client_mcp(client) -> str:
    r = await client.post(
        "/api/v1/oauth/register",
        json={"redirect_uris": ["http://localhost:14567/callback"], "client_name": "Claude Code"},
    )
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


@pytest.mark.asyncio
async def test_sans_session_la_connexion_garde_tout_le_chemin_de_retour(client):
    client_id = await _client_mcp(client)
    r = await client.get(
        "/api/v1/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "http://localhost:14567/callback",
            "code_challenge": "abc",
            "code_challenge_method": "S256",
            "state": "etat-du-client",
        },
    )
    assert r.status_code == 302
    cible = urlparse(r.headers["location"])
    assert cible.path == "/api/v1/auth/google/login"
    retour = parse_qs(cible.query)["return_to"][0]
    assert retour.startswith("/api/v1/oauth/authorize?")
    # Le `state` du client et son `redirect_uri` survivent au detour.
    assert "state=etat-du-client" in retour
    assert "redirect_uri=" in retour


@pytest.mark.asyncio
async def test_la_connexion_retient_un_retour_vers_l_autorisation(client):
    r = await client.get(
        "/api/v1/auth/google/login",
        params={"return_to": "/api/v1/oauth/authorize?client_id=x"},
    )
    assert r.status_code == 302
    assert auth_endpoints.RETURN_TO_COOKIE in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retour", ["https://ailleurs.test/piege", "//ailleurs.test/piege", "/dashboard"]
)
async def test_un_retour_hors_autorisation_n_est_jamais_retenu(client, retour):
    r = await client.get("/api/v1/auth/google/login", params={"return_to": retour})
    assert r.status_code == 302
    assert auth_endpoints.RETURN_TO_COOKIE not in r.headers.get("set-cookie", "")


def test_apres_connexion_le_retour_retenu_l_emporte():
    demande = SimpleNamespace(
        cookies={auth_endpoints.RETURN_TO_COOKIE: "/api/v1/oauth/authorize?client_id=x"}
    )
    assert (
        auth_endpoints._destination_apres_connexion(demande)
        == "/api/v1/oauth/authorize?client_id=x"
    )


def test_sans_retour_la_connexion_mene_a_l_accueil_connecte():
    demande = SimpleNamespace(cookies={auth_endpoints.RETURN_TO_COOKIE: "https://ailleurs.test"})
    assert auth_endpoints._destination_apres_connexion(demande).endswith("/auth/callback")


@pytest.mark.asyncio
async def test_en_production_l_autorisation_est_servie_par_le_site(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "frontend_base_url", "https://site.test")
    r = await client.get("/.well-known/oauth-authorization-server")
    donnees = r.json()
    assert donnees["authorization_endpoint"] == "https://site.test/api/v1/oauth/authorize"
    # Le jeton et l'inscription restent sur l'API : ils n'ont pas besoin de session.
    assert not donnees["token_endpoint"].startswith("https://site.test")
