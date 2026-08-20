"""Tests d'intégration des sessions de chat de l'agent et de `POST /agent/approve`."""

from __future__ import annotations

import asyncio
import json
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
from app.services import agent_approvals


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


async def _autre_createur(db_session, auth_service) -> str:
    autre = User(
        id=uuid4(),
        email="autre-sessions@example.com",
        username="autresessions",
        display_name="Autre",
        public_key="s" * 64,
        encrypted_private_key="enc",
        google_id="google_autre_sessions",
        is_verified=True,
    )
    db_session.add(autre)
    await db_session.commit()
    return auth_service.create_session(autre.id)


async def _inserer_provider_defaut(db_session, test_user) -> AgentProvider:
    p = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url="https://api.openai.com",
        model="gpt-4o-mini",
        api_key_enc=KeyManager(get_settings().master_encryption_key).encrypt_private_key(
            "sk-test-12345678"
        ),
        is_default=True,
    )
    db_session.add(p)
    await db_session.commit()
    return p


def _lire_evenements(texte: str) -> list[dict]:
    events = []
    for bloc in texte.split("\n\n"):
        ligne = bloc.strip().split("\n", 1)[0]
        if ligne.startswith("data: "):
            events.append(json.loads(ligne[len("data: ") :]))
    return events


def _mock_texte(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}], "usage": {}}


@pytest.mark.asyncio
async def test_sessions_requiert_auth(client):
    assert (await client.get("/api/v1/agent/sessions")).status_code == 401


@pytest.mark.asyncio
async def test_creer_lister_supprimer(client, session_token):
    client.cookies.set("filum_session", session_token)

    creation = await client.post("/api/v1/agent/sessions", json={"title": "Fiche fusion"})
    assert creation.status_code == 201
    session_id = creation.json()["id"]

    liste = await client.get("/api/v1/agent/sessions")
    assert [s["id"] for s in liste.json()] == [session_id]

    assert (await client.delete(f"/api/v1/agent/sessions/{session_id}")).status_code == 204
    assert (await client.get("/api/v1/agent/sessions")).json() == []


@pytest.mark.asyncio
async def test_session_dun_autre_createur_est_404(client, session_token, db_session, auth_service):
    client.cookies.set("filum_session", session_token)
    session_id = (await client.post("/api/v1/agent/sessions", json={})).json()["id"]

    client.cookies.set("filum_session", await _autre_createur(db_session, auth_service))
    assert (await client.get(f"/api/v1/agent/sessions/{session_id}/messages")).status_code == 404
    assert (await client.delete(f"/api/v1/agent/sessions/{session_id}")).status_code == 404


@pytest.mark.asyncio
async def test_le_tour_est_persiste_et_repris(client, session_token, db_session, test_user):
    await _inserer_provider_defaut(db_session, test_user)
    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, json=_mock_texte("Bonjour."))
    )
    client.cookies.set("filum_session", session_token)

    premier = await client.post("/api/v1/agent/chat", json={"message": "salut"})
    events = _lire_evenements(premier.text)
    assert events[0]["type"] == "session"
    session_id = events[0]["payload"]["id"]

    messages = (await client.get(f"/api/v1/agent/sessions/{session_id}/messages")).json()
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "salut"),
        ("assistant", "Bonjour."),
    ]

    # Poursuivre la même session ne crée pas de doublon et garde l'historique.
    suite = await client.post(
        "/api/v1/agent/chat", json={"message": "encore", "session_id": session_id}
    )
    assert _lire_evenements(suite.text)[0]["payload"]["id"] == session_id
    messages = (await client.get(f"/api/v1/agent/sessions/{session_id}/messages")).json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

    sessions = (await client.get("/api/v1/agent/sessions")).json()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "salut"


@pytest.mark.asyncio
async def test_chat_sur_session_inconnue_est_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post(
        "/api/v1/agent/chat", json={"message": "salut", "session_id": str(uuid4())}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_debloque_la_boucle(client, session_token, test_user):
    client.cookies.set("filum_session", session_token)
    request_id = str(uuid4())
    attente = asyncio.create_task(agent_approvals.attendre(request_id, test_user.id, delai=5))
    await asyncio.sleep(0)

    reponse = await client.post(
        "/api/v1/agent/approve", json={"request_id": request_id, "approved": True}
    )
    assert reponse.status_code == 204
    assert await attente is True


@pytest.mark.asyncio
async def test_approve_dun_autre_createur_est_404(
    client, session_token, test_user, db_session, auth_service
):
    request_id = str(uuid4())
    attente = asyncio.create_task(agent_approvals.attendre(request_id, test_user.id, delai=0.5))
    await asyncio.sleep(0)

    client.cookies.set("filum_session", await _autre_createur(db_session, auth_service))
    reponse = await client.post(
        "/api/v1/agent/approve", json={"request_id": request_id, "approved": True}
    )
    assert reponse.status_code == 404
    # La demande n'a pas été volée : elle expire en refus.
    assert await attente is False


@pytest.mark.asyncio
async def test_approve_identifiant_inconnu_est_404(client, session_token):
    client.cookies.set("filum_session", session_token)
    reponse = await client.post(
        "/api/v1/agent/approve", json={"request_id": str(uuid4()), "approved": True}
    )
    assert reponse.status_code == 404
