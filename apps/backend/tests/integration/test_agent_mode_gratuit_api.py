"""Tests d'integration du mode gratuit : endpoints de consentement + chat SSE.

Le chat est teste avec un ``httpx.MockTransport`` : le chemin reel (routeur
de lanes, provider transient, banniere, quotas) est exerce, seul l'appel
HTTP sortant vers Z.ai est simule.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints.agent_providers import get_http_client
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.main import app
from app.models.agent_lane import AgentLane
from app.services import agent_gratuit


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def settings_actives(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "agent_gratuit_enabled", True)
    monkeypatch.setattr(s, "agent_gratuit_zai_api_key", "zai-key-test")
    return s


@pytest_asyncio.fixture
async def lane_zai(db_session):
    lane = AgentLane(
        id=uuid4(),
        slug="zai",
        label_public="GLM · Z.ai",
        provider_kind="custom",
        base_url="https://api.z.ai/api/paas/v4",
        model="glm-5.2",
        rpm_cap=3,
        rpd_cap=900,
        actif=True,
        position=0,
    )
    db_session.add(lane)
    await db_session.commit()
    await db_session.refresh(lane)
    return lane


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


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


# ---------------------------------------------------------------------------
# Endpoints de consentement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_etat_indisponible_sans_config(client, session_token):
    client.cookies.set("filum_session", session_token)
    r = await client.get("/api/v1/agent/mode-gratuit")
    assert r.status_code == 200
    body = r.json()
    assert body["disponible"] is False and body["actif"] is False


@pytest.mark.asyncio
async def test_consentement_aller_retour(client, session_token, settings_actives, lane_zai):
    client.cookies.set("filum_session", session_token)
    # Version erronee : refusee (le handler global enveloppe dans {"error": ...}).
    r = await client.put("/api/v1/agent/mode-gratuit", json={"version": "mauvaise-version"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "version_warning_inconnue"
    # Bonne version : active, et l'etat nomme le fournisseur qui sert le tour.
    r = await client.put(
        "/api/v1/agent/mode-gratuit", json={"version": agent_gratuit.VERSION_WARNING}
    )
    assert r.status_code == 200 and r.json()["actif"] is True
    etat = (await client.get("/api/v1/agent/mode-gratuit")).json()
    assert etat["actif"] is True
    assert etat["fournisseur_actuel"] == lane_zai.label_public
    # Retrait.
    r = await client.delete("/api/v1/agent/mode-gratuit")
    assert r.status_code == 200
    etat = (await client.get("/api/v1/agent/mode-gratuit")).json()
    assert etat["actif"] is False
    assert etat["fournisseur_actuel"] is None


# ---------------------------------------------------------------------------
# Chat : la lane sert le tour quand l'utilisateur a consenti
# ---------------------------------------------------------------------------


def _mock_reponse_glm(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}], "usage": {}}


@pytest.mark.asyncio
async def test_chat_mode_gratuit_emet_la_banniere(
    client, session_token, db_session, test_user, settings_actives, lane_zai
):
    await agent_gratuit.donner_consentement(db_session, test_user.id, agent_gratuit.VERSION_WARNING)

    def handler(request):
        assert str(request.url).startswith("https://api.z.ai/api/paas/v4/chat/completions")
        assert request.headers["Authorization"] == "Bearer zai-key-test"
        return httpx.Response(200, json=_mock_reponse_glm("Reponse gratuite."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)

    client.cookies.set("filum_session", session_token)
    r = await client.post("/api/v1/agent/chat", json={"message": "salut"})
    assert r.status_code == 200
    events = _lire_evenements(r.text)
    types = [e["type"] for e in events]
    assert "gratuit_actif" in types
    banniere = events[types.index("gratuit_actif")]["payload"]
    assert banniere["provider_public_name"] == "GLM · Z.ai"
    assert "entrainer" in banniere["retention_notice"]
    assert events[-2]["payload"]["delta"] == "Reponse gratuite."
    assert types[-1] == "done"

    # Le tour a consomme la lane ET le quota utilisateur.
    reste = await agent_gratuit.verifier_quota_utilisateur(db_session, test_user.id)
    assert reste == get_settings().agent_gratuit_daily_quota_messages - 1


@pytest.mark.asyncio
async def test_chat_sans_consentement_nutilise_pas_la_lane(
    client, session_token, settings_actives, lane_zai
):
    """Sans consentement : erreur standard, jamais la cle serveur."""
    client.cookies.set("filum_session", session_token)
    r = await client.post("/api/v1/agent/chat", json={"message": "salut"})
    events = _lire_evenements(r.text)
    assert events[-1]["type"] == "error"
    assert "Aucune clé IA disponible" in events[-1]["payload"]["message"]
