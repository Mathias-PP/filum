from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints.agent_providers import get_http_client
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.crypto.keygen import KeyManager
from app.db.database import get_db
from app.main import app
from app.models.agent_provider import AgentProvider
from app.models.user import User


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _cle_chiffree(key: str) -> str:
    return KeyManager(get_settings().master_encryption_key).encrypt_private_key(key)


async def _inserer_provider(
    db_session,
    creator_id,
    *,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    key: str = "sk-abcdef1234",
    base_url: str = "https://api.openai.com",
    is_default: bool = False,
) -> AgentProvider:
    p = AgentProvider(
        creator_id=creator_id,
        provider=provider,
        display_name=provider,
        base_url=base_url,
        model=model,
        api_key_enc=_cle_chiffree(key),
        is_default=is_default,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.mark.asyncio
async def test_requires_auth(client):
    response = await client.get("/api/v1/agent/providers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_meta_public(client):
    response = await client.get("/api/v1/agent/providers/meta")
    assert response.status_code == 200
    body = response.json()
    assert "data_scope" in body
    assert set(body["providers"]) == {"openai", "anthropic", "deepseek", "gemini", "custom"}
    assert "Chine" in body["providers"]["deepseek"]["hosting_country"]
    assert "vos messages" in body["data_scope"]
    assert "clé api" in body["data_scope"].lower()


@pytest.mark.asyncio
async def test_create_list_masque(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/providers",
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "sk-secret-12345678",
            "is_default": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "openai"
    assert body["base_url"] == "https://api.openai.com"
    assert body["is_default"] is True
    assert body["api_key_masked"] == "sk-…5678"
    assert "api_key" not in body

    response = await client.get("/api/v1/agent/providers")
    assert response.status_code == 200
    liste = response.json()
    assert len(liste) == 1
    assert "api_key" not in liste[0]


@pytest.mark.asyncio
async def test_doublon_refuse_400(client, session_token):
    client.cookies.set("filum_session", session_token)
    payload = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": "sk-aaaa1111",
    }
    assert (await client.post("/api/v1/agent/providers", json=payload)).status_code == 201
    response = await client.post("/api/v1/agent/providers", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_extra_forbid_422(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/providers",
        json={"provider": "openai", "model": "m", "api_key": "k", "spam": "oui"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_custom_exige_base_url_400(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/providers",
        json={"provider": "custom", "model": "mon-modele", "api_key": "k"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_custom_url_non_http_422(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/providers",
        json={
            "provider": "custom",
            "model": "mon-modele",
            "api_key": "k",
            "base_url": "ftp://example.com",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_custom_base_url_privee_400(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/providers",
        json={
            "provider": "custom",
            "model": "mon-modele",
            "api_key": "k",
            "base_url": "http://127.0.0.1:8000",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_un_seul_defaut(client, session_token):
    client.cookies.set("filum_session", session_token)
    premier = await client.post(
        "/api/v1/agent/providers",
        json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "k1", "is_default": True},
    )
    assert premier.status_code == 201
    premier_id = premier.json()["id"]

    second = await client.post(
        "/api/v1/agent/providers",
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "k2",
            "is_default": True,
        },
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    liste = {p["id"]: p for p in (await client.get("/api/v1/agent/providers")).json()}
    assert liste[premier_id]["is_default"] is False
    assert liste[second_id]["is_default"] is True


@pytest.mark.asyncio
async def test_patch_cle_et_defaut(client, session_token):
    client.cookies.set("filum_session", session_token)
    created = await client.post(
        "/api/v1/agent/providers",
        json={"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "sk-ancienne9999"},
    )
    provider_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/agent/providers/{provider_id}",
        json={"api_key": "sk-nouvelle8888", "is_default": True, "display_name": "Gemini perso"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["api_key_masked"] == "sk-…8888"
    assert body["is_default"] is True
    assert body["display_name"] == "Gemini perso"


@pytest.mark.asyncio
async def test_patch_inconnu_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.patch(
        f"/api/v1/agent/providers/{uuid4()}",
        json={"display_name": "rien"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete(client, session_token, db_session, test_user):
    provider = await _inserer_provider(db_session, test_user.id)
    client.cookies.set("filum_session", session_token)

    response = await client.delete(f"/api/v1/agent/providers/{provider.id}")
    assert response.status_code == 204

    response = await client.get("/api/v1/agent/providers")
    assert response.json() == []


@pytest.mark.asyncio
async def test_isolation_entre_createurs(client, db_session, test_user, auth_service):
    provider = await _inserer_provider(db_session, test_user.id)

    autre = User(
        id=uuid4(),
        email="autre@example.com",
        username="autrecreateur",
        display_name="Autre",
        public_key="o" * 64,
        encrypted_private_key="enc",
        google_id="google_autre_1",
        is_verified=True,
    )
    db_session.add(autre)
    await db_session.commit()
    token_autre = auth_service.create_session(autre.id)
    client.cookies.set("filum_session", token_autre)

    response = await client.get("/api/v1/agent/providers")
    assert response.status_code == 200
    assert response.json() == []

    response = await client.patch(
        f"/api/v1/agent/providers/{provider.id}", json={"display_name": "Hack"}
    )
    assert response.status_code == 404

    response = await client.delete(f"/api/v1/agent/providers/{provider.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_cle_route_ok(client, session_token, db_session, test_user):
    provider = await _inserer_provider(db_session, test_user.id)
    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, json={})
    )
    client.cookies.set("filum_session", session_token)

    response = await client.post(f"/api/v1/agent/providers/{provider.id}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model_resolved"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_test_cle_route_invalide(client, session_token, db_session, test_user):
    provider = await _inserer_provider(db_session, test_user.id)
    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(
        lambda request: httpx.Response(401, json={})
    )
    client.cookies.set("filum_session", session_token)

    response = await client.post(f"/api/v1/agent/providers/{provider.id}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "Clé API invalide" in body["message"]


@pytest.mark.asyncio
async def test_test_cle_inconnu_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(f"/api/v1/agent/providers/{uuid4()}/test")
    assert response.status_code == 404
