"""Tests d'intégration du run de fiche : lancement SSE et suivi d'avancement."""

from __future__ import annotations

import json
from uuid import UUID

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
from app.services import agent_fiche, agent_sessions, agent_workspace


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
    app.dependency_overrides[get_approver] = lambda: lambda creator_id: _refuse
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _refuse(request_id, tool, args) -> bool:
    return False


async def _provider_defaut(db_session, test_user) -> AgentProvider:
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


async def _stages(db_session, creator_id) -> None:
    for etape in agent_fiche.ETAPES:
        await agent_workspace.ecrire(
            db_session, creator_id, etape.instructions, f"Règles de {etape.id}."
        )
    await db_session.commit()


def _transport_texte() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "fait"}}], "usage": {}},
        )

    return httpx.MockTransport(handler)


def _evenements(texte: str) -> list[dict]:
    events = []
    for bloc in texte.split("\n\n"):
        ligne = bloc.strip().split("\n", 1)[0]
        if ligne.startswith("data: "):
            events.append(json.loads(ligne[len("data: ") :]))
    return events


def _corps(**extra) -> dict:
    return {"content_url": "https://exemple.test/video", "slug": "ma-fiche", **extra}


@pytest.mark.asyncio
async def test_lancement_requiert_auth(client):
    response = await client.post("/api/v1/agent/fiche", json=_corps())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lancement_sans_provider_defaut(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post("/api/v1/agent/fiche", json=_corps())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_default_provider"


@pytest.mark.asyncio
async def test_slug_invalide_refuse(client, session_token, db_session, test_user):
    await _provider_defaut(db_session, test_user)
    client.cookies.set("filum_session", session_token)
    response = await client.post("/api/v1/agent/fiche", json=_corps(slug="Pas Un Slug"))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_complet_trace_les_etages(client, session_token, db_session, test_user):
    await _provider_defaut(db_session, test_user)
    await _stages(db_session, test_user.id)
    app.dependency_overrides[get_http_client] = lambda: _transport_texte()
    client.cookies.set("filum_session", session_token)

    response = await client.post("/api/v1/agent/fiche", json=_corps())

    assert response.status_code == 200
    events = _evenements(response.text)
    assert events[0]["type"] == "session"
    faits = [e["payload"]["stage"] for e in events if e["type"] == "stage_done"]
    assert faits == [e.id for e in agent_fiche.ETAPES]
    assert events[-1]["payload"]["reason"] == "fiche_complete"

    session_id = events[0]["payload"]["id"]
    journal = await agent_sessions.messages(db_session, test_user.id, UUID(session_id))
    assert journal[0].role == "user"
    assert "07-publication" in journal[-1].content


@pytest.mark.asyncio
async def test_regles_absentes_rendent_une_erreur_lisible(
    client, session_token, db_session, test_user
):
    """Sans workspace seedé, le run doit le dire au lieu de planter le flux."""
    await _provider_defaut(db_session, test_user)
    app.dependency_overrides[get_http_client] = lambda: _transport_texte()
    client.cookies.set("filum_session", session_token)

    response = await client.post("/api/v1/agent/fiche", json=_corps())

    events = _evenements(response.text)
    assert events[-1]["type"] == "error"
    assert "01-brief" in events[-1]["payload"]["message"]


@pytest.mark.asyncio
async def test_etat_du_run(client, session_token, db_session, test_user):
    await agent_workspace.ecrire(db_session, test_user.id, "runs/ma-fiche/00-brief.md", "le brief")
    await db_session.commit()
    client.cookies.set("filum_session", session_token)

    response = await client.get("/api/v1/agent/fiche/ma-fiche")

    assert response.status_code == 200
    corps = response.json()
    assert corps["demarre"] is True
    assert [e["id"] for e in corps["etapes"] if e["fait"]] == ["01-brief"]
