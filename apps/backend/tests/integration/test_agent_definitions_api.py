from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.main import app


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


@pytest.mark.asyncio
async def test_requires_auth(client):
    assert (await client.get("/api/v1/agent/definitions")).status_code == 401
    assert (await client.get("/api/v1/agent/definitions/assistant")).status_code == 401


@pytest.mark.asyncio
async def test_liste_seed_au_premier_acces(client, session_token):
    """Un createur qui n'a jamais ouvert son workspace voit quand meme ses agents."""
    client.cookies.set("filum_session", session_token)
    response = await client.get("/api/v1/agent/definitions")
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == []

    par_slug = {a["slug"]: a for a in body["agents"]}
    assert "assistant" in par_slug
    assistant = par_slug["assistant"]
    assert assistant["builtin"] is True
    assert assistant["tools"]
    assert assistant["path"] == "agents/assistant.yaml"
    assert body["agents"][0]["slug"] == "assistant"


@pytest.mark.asyncio
async def test_obtenir_un_agent(client, session_token):
    client.cookies.set("filum_session", session_token)
    await client.get("/api/v1/agent/definitions")

    response = await client.get("/api/v1/agent/definitions/relecteur")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "relecteur"
    assert body["system_prompt"]
    assert body["contract"]


@pytest.mark.asyncio
async def test_agent_inconnu_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.get("/api/v1/agent/definitions/fantome")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "agent_not_found"


@pytest.mark.asyncio
async def test_fichier_casse_apparait_en_rejet(client, session_token):
    """Un agent invalide doit se voir, sinon il disparait sans explication."""
    client.cookies.set("filum_session", session_token)
    await client.put(
        "/api/v1/agent/workspace/file",
        params={"path": "agents/casse.yaml"},
        json={"content": "slug: casse\nname: Casse\n"},
    )

    response = await client.get("/api/v1/agent/definitions")
    assert response.status_code == 200
    body = response.json()
    assert [r["path"] for r in body["rejected"]] == ["agents/casse.yaml"]
    assert body["rejected"][0]["raison"]
    assert "casse" not in {a["slug"] for a in body["agents"]}
