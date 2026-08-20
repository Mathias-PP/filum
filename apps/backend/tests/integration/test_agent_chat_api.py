"""Tests d'intégration de l'endpoint chat de l'agent (flux SSE)."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints.agent_chat import get_approver
from app.api.v1.endpoints.agent_providers import get_http_client
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.crypto.keygen import KeyManager
from app.db.database import get_db
from app.main import app
from app.models.agent_provider import AgentProvider


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


async def _inserer_provider_defaut(db_session, test_user, *, model="gpt-4o-mini") -> AgentProvider:
    p = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url="https://api.openai.com",
        model=model,
        api_key_enc=_cle_chiffree("sk-test-12345678"),
        is_default=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


def _lire_evenements(texte: str) -> list[dict]:
    events = []
    for bloc in texte.split("\n\n"):
        bloc = bloc.strip()
        if not bloc:
            continue
        ligne = bloc.split("\n", 1)[0]
        if ligne.startswith("data: "):
            events.append(json.loads(ligne[len("data: ") :]))
    return events


def _mock_texte(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}], "usage": {}}


def _mock_tool_call(name: str, arguments: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ],
        "usage": {},
    }


async def _post_chat(client, message: str) -> httpx.Response:
    return await client.post(
        "/api/v1/agent/chat",
        json={"message": message, "history": [{"role": "user", "content": "contexte"}]},
    )


@pytest.mark.asyncio
async def test_chat_requiert_auth(client):
    response = await _post_chat(client, "bonjour")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_sans_provider_defaut(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await _post_chat(client, "bonjour")
    assert response.status_code == 200
    events = _lire_evenements(response.text)
    assert events[-1]["type"] == "error"
    assert "Aucun provider IA par défaut" in events[-1]["payload"]["message"]


@pytest.mark.asyncio
async def test_chat_flux_complet(client, session_token, db_session, test_user):
    await _inserer_provider_defaut(db_session, test_user)
    appels = {"n": 0}

    def handler(request):
        appels["n"] += 1
        if appels["n"] == 1:
            return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "étoiles"}))
        return httpx.Response(200, json=_mock_texte("Voilà ce que j'ai trouvé."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)

    async def approuve(tool, args):
        return True

    app.dependency_overrides[get_approver] = lambda: approuve
    client.cookies.set("filum_session", session_token)

    response = await _post_chat(client, "cherche étoiles")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _lire_evenements(response.text)
    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "message_delta", "done"]
    assert events[1]["payload"]["result"]["error"]  # web_search non configurée en test
    assert events[2]["payload"]["delta"] == "Voilà ce que j'ai trouvé."


@pytest.mark.asyncio
async def test_chat_action_sensible_refusee_par_defaut(client, session_token, db_session, test_user):
    await _inserer_provider_defaut(db_session, test_user)
    appels = {"n": 0}

    def handler(request):
        appels["n"] += 1
        if appels["n"] == 1:
            return httpx.Response(200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"}))
        return httpx.Response(200, json=_mock_texte("D'accord, je m'arrête."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)
    client.cookies.set("filum_session", session_token)

    response = await _post_chat(client, "publie ma fiche")
    events = _lire_evenements(response.text)
    types = [e["type"] for e in events]
    assert "approval_request" in types
    assert "approval_resolved" in types
    assert events[types.index("approval_resolved")]["payload"]["approved"] is False
    resultat = events[types.index("tool_result")]["payload"]["result"]
    assert "refusée" in resultat["error"]
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_chat_nemprunte_pas_le_provider_dun_autre(
    client, db_session, test_user, auth_service
):
    await _inserer_provider_defaut(db_session, test_user)

    autre = __import__("app.models.user", fromlist=["User"]).User(
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

    response = await _post_chat(client, "bonjour")
    events = _lire_evenements(response.text)
    # L'autre créateur n'a pas de provider : erreur, jamais l'accès à celui du premier.
    assert events[-1]["type"] == "error"
    assert "Aucun provider" in events[-1]["payload"]["message"]
