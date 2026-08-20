from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.main import app
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


@pytest.mark.asyncio
async def test_requires_auth(client):
    assert (await client.get("/api/v1/agent/workspace/tree")).status_code == 401
    assert (
        await client.get("/api/v1/agent/workspace/file", params={"path": "AGENTS.md"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_tree_seed_au_premier_acces(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.get("/api/v1/agent/workspace/tree")
    assert response.status_code == 200
    arbre = response.json()
    chemins = {e["path"] for e in arbre}
    assert "AGENTS.md" in chemins
    assert "shared/principes-editoriaux.md" in chemins
    assert "stages/07-publication/CONTEXT.md" in chemins


@pytest.mark.asyncio
async def test_ecrire_lire_fichier(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.put(
        "/api/v1/agent/workspace/file",
        params={"path": "agents/mon-agent.yaml"},
        json={"content": "name: mon-agent\n"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "agents/mon-agent.yaml"
    assert body["sha256"]

    response = await client.get(
        "/api/v1/agent/workspace/file",
        params={"path": "agents/mon-agent.yaml"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "name: mon-agent\n"


@pytest.mark.asyncio
async def test_ecrire_chemin_invalide_400(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.put(
        "/api/v1/agent/workspace/file",
        params={"path": "../../etc/passwd"},
        json={"content": "x"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ecrire_extra_forbid_422(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.put(
        "/api/v1/agent/workspace/file",
        params={"path": "shared/a.md"},
        json={"content": "x", "spam": "oui"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_lire_inconnu_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.get(
        "/api/v1/agent/workspace/file", params={"path": "runs/jamais-existe.md"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_supprimer_fichier(client, session_token):
    client.cookies.set("filum_session", session_token)
    await client.put(
        "/api/v1/agent/workspace/file", params={"path": "runs/a/00-brief.md"}, json={"content": "x"}
    )
    response = await client.delete(
        "/api/v1/agent/workspace/file", params={"path": "runs/a/00-brief.md"}
    )
    assert response.status_code == 204
    assert (
        await client.get("/api/v1/agent/workspace/file", params={"path": "runs/a/00-brief.md"})
    ).status_code == 404


@pytest.mark.asyncio
async def test_seed_explicite_idempotent(client, session_token):
    client.cookies.set("filum_session", session_token)
    premier = await client.post("/api/v1/agent/workspace/seed")
    assert premier.status_code == 200
    assert premier.json()["seeded"] > 0

    second = await client.post("/api/v1/agent/workspace/seed")
    assert second.status_code == 200
    assert second.json()["seeded"] == 0


@pytest.mark.asyncio
async def test_isolation_entre_createurs(client, db_session, test_user, auth_service):
    client.cookies.set("filum_session", auth_service.create_session(test_user.id))
    await client.put(
        "/api/v1/agent/workspace/file",
        params={"path": "runs/moi/00-brief.md"},
        json={"content": "privé"},
    )

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

    response = await client.get(
        "/api/v1/agent/workspace/file", params={"path": "runs/moi/00-brief.md"}
    )
    assert response.status_code == 404

    response = await client.delete(
        "/api/v1/agent/workspace/file", params={"path": "runs/moi/00-brief.md"}
    )
    assert response.status_code == 404
