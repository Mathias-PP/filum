"""Tests d'intégration de l'endpoint chat de l'agent (flux SSE)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.endpoints.agent_chat import (
    _blocs_complets,
    _reponse_finale,
    _texte_interrompu,
    get_approver,
)
from app.api.v1.endpoints.agent_providers import get_http_client
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.crypto.keygen import KeyManager
from app.db.database import async_session_maker, get_db
from app.main import app
from app.models.agent_provider import AgentProvider
from app.models.agent_session import AgentMessage
from app.services import agent_tours


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


def _mock_tool_call(name: str, arguments: dict, content: str | None = None) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
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


def _scope_chat(corps: bytes, session_token: str) -> dict:
    """Un scope ASGI minimal pour ``POST /agent/chat``, cookie de session compris."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/agent/chat",
        "raw_path": b"/api/v1/agent/chat",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(corps)).encode()),
            (b"cookie", f"filum_session={session_token}".encode()),
        ],
        "client": ("127.0.0.1", 51234),
        "server": ("test", 80),
    }


async def _messages_persistes(session_id: str) -> list[tuple[str, str]]:
    """Les (rôle, contenu) écrits en base, dans l'ordre.

    Session dédiée : ``_persister_tour`` écrit par la sienne, celle du test ne
    verrait pas forcément la validation.
    """
    async with async_session_maker() as db:
        resultat = await db.execute(
            select(AgentMessage.role, AgentMessage.content)
            .where(AgentMessage.session_id == UUID(session_id))
            .order_by(AgentMessage.created_at, AgentMessage.id)
        )
        return [(r, c or "") for r, c in resultat.all()]


async def _post_chat(client, message: str) -> httpx.Response:
    return await client.post(
        "/api/v1/agent/chat",
        json={"message": message, "history": [{"role": "user", "content": "contexte"}]},
    )


class TestTourInterrompu:
    """Un client qui part en cours de tour ne doit pas effacer ce tour.

    Les écritures d'outils, elles, sont déjà en base : sans rattrapage, la
    source que l'agent vient de créer existe sans figurer dans la
    conversation, et le tour suivant la recrée.
    """

    @staticmethod
    def _assistant(nb_appels: int) -> dict:
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": f"call_{i}", "type": "function", "function": {"name": "web_search"}}
                for i in range(nb_appels)
            ],
        }

    @staticmethod
    def _tool(i: int) -> dict:
        return {"role": "tool", "tool_call_id": f"call_{i}", "name": "web_search", "content": "{}"}

    def test_un_tour_complet_passe_entier(self):
        ajouts = [self._assistant(2), self._tool(0), self._tool(1)]
        assert _blocs_complets(ajouts) == ajouts

    def test_un_appel_sans_reponse_est_coupe(self):
        # Un tool_calls orphelin fait rejeter le tour suivant par tous les
        # fournisseurs : mieux vaut perdre l'appel amorcé que la session.
        ajouts = [self._assistant(1), self._tool(0), self._assistant(2), self._tool(0)]
        assert _blocs_complets(ajouts) == ajouts[:2]

    def test_un_tour_sans_outil_passe_entier(self):
        ajouts = [{"role": "assistant", "content": "Voilà."}]
        assert _blocs_complets(ajouts) == ajouts

    def test_rien_a_persister_ne_leve_pas(self):
        assert _blocs_complets([]) == []

    def test_une_reponse_coupee_le_dit(self):
        assert "interrompue" in _texte_interrompu("Je commen")
        assert _texte_interrompu("") == ""

    @pytest.mark.asyncio
    async def test_le_tour_est_persiste_meme_si_le_client_part(
        self, client, session_token, db_session, test_user
    ):
        # Appel ASGI brut : ``ASGITransport`` de httpx bufferise la reponse
        # entiere, donc un client qui cesse de lire n'y coupe rien. On rejoue
        # ce que fait un vrai serveur : une erreur sur ``send`` des que le
        # socket est tombe.
        await _inserer_provider_defaut(db_session, test_user)
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "x"}))
            return httpx.Response(200, json=_mock_texte("Voilà ce que j'ai trouvé."))

        app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)
        corps = json.dumps({"message": "cherche", "history": []}).encode()
        recus: list[dict] = []

        demandes = {"n": 0}
        jamais = asyncio.Event()

        async def receive():
            # Le corps une fois, puis plus rien : Starlette ecoute la
            # deconnexion sur ce meme ``receive``, et lui rendre tout de suite
            # un ``http.disconnect`` couperait le flux avant le premier tour.
            demandes["n"] += 1
            if demandes["n"] == 1:
                return {"type": "http.request", "body": corps, "more_body": False}
            await jamais.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            recus.append(message)
            # Partir au premier morceau de reponse : l'outil a deja ecrit en
            # base, et c'est la que la conversation risque de ne pas le savoir.
            if b'"message_delta"' in message.get("body", b""):
                raise ConnectionResetError("le client est parti")

        with contextlib.suppress(ConnectionResetError):
            await app(_scope_chat(corps, session_token), receive, send)

        evenements = [
            json.loads(m["body"].decode()[6:])
            for m in recus
            if m["type"] == "http.response.body" and m["body"].startswith(b"data: ")
        ]
        session_id = evenements[0]["payload"]["id"]

        # Le tour ne vit plus dans le flux : il continue sans le client et
        # s'ecrit en entier, reponse finale comprise, sans marque de coupure.
        messages: list[tuple[str, str]] = []
        for _ in range(200):
            messages = await _messages_persistes(session_id)
            if len(messages) > 1:
                break
            await asyncio.sleep(0.02)
        roles = [r for r, _ in messages]
        assert roles == ["user", "assistant", "tool", "assistant"]
        assert messages[-1][1] == "Voilà ce que j'ai trouvé."


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
    assert "Aucune clé IA disponible" in events[-1]["payload"]["message"]


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

    async def approuve(request_id, tool, args):
        return True

    app.dependency_overrides[get_approver] = lambda: lambda creator_id: approuve
    client.cookies.set("filum_session", session_token)

    response = await _post_chat(client, "cherche étoiles")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _lire_evenements(response.text)
    types = [e["type"] for e in events]
    assert types == ["session", "tool_call", "tool_result", "message_delta", "done"]
    assert events[2]["payload"]["result"]["error"]  # web_search non configurée en test
    assert events[3]["payload"]["delta"] == "Voilà ce que j'ai trouvé."


@pytest.mark.asyncio
async def test_chat_action_sensible_refusee(client, session_token, db_session, test_user):
    await _inserer_provider_defaut(db_session, test_user)
    appels = {"n": 0}

    def handler(request):
        appels["n"] += 1
        if appels["n"] == 1:
            return httpx.Response(200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"}))
        return httpx.Response(200, json=_mock_texte("D'accord, je m'arrête."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)

    async def refuse(request_id, tool, args):
        return False

    app.dependency_overrides[get_approver] = lambda: lambda creator_id: refuse
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
    assert "Aucune clé IA disponible" in events[-1]["payload"]["message"]


@pytest.mark.asyncio
async def test_la_consigne_de_controle_ne_reste_pas_dans_l_historique(
    client, session_token, db_session, test_user
):
    """La relance pose un message système ; il ne doit pas être persisté.

    Le prompt système est reconstruit en tête à chaque tour. Un second message
    système dans l'historique fait refuser l'appel chez Gemini, et la consigne
    ne vaut que pour le tour où elle a été posée.
    """
    await _inserer_provider_defaut(db_session, test_user)
    appels = {"n": 0}

    def handler(request):
        appels["n"] += 1
        if appels["n"] == 1:
            return httpx.Response(200, json=_mock_texte("J'ai créé la fiche."))
        return httpx.Response(200, json=_mock_texte("Rien n'a été créé, la source est illisible."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)
    client.cookies.set("filum_session", session_token)
    try:
        response = await _post_chat(client, "crée une fiche")
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    events = _lire_evenements(response.text)
    assert any(e["type"] == "controle_relance" for e in events)
    assert appels["n"] == 2

    session_id = next(e["payload"]["id"] for e in events if e["type"] == "session")
    roles = [r for r, _ in await _messages_persistes(session_id)]
    assert "system" not in roles


class TestReponseFinale:
    """La réponse persistée est le texte du dernier appel au modèle, seul."""

    def test_le_plan_du_debut_n_est_pas_recolle(self):
        deltas = {1: ["Je vais poser trois extraits."], 2: ["Deux extraits posés."]}
        assert _reponse_finale(deltas, []) == "Deux extraits posés."

    def test_un_texte_deja_porte_par_un_appel_n_est_pas_double(self):
        ajouts = [{"role": "assistant", "content": "Je lis la page.", "tool_calls": [{}]}]
        assert _reponse_finale({1: ["Je lis la page."]}, ajouts) == ""

    def test_sans_texte(self):
        assert _reponse_finale({}, []) == ""


def _code_erreur(response: httpx.Response) -> str:
    """Le code d'une erreur HTTP, quelle que soit l'enveloppe posee par l'application."""
    corps = response.json()
    return (corps.get("error") or corps.get("detail"))["code"]


async def _session_apres_un_tour(client, session_token, db_session, test_user) -> str:
    await _inserer_provider_defaut(db_session, test_user)
    appels = {"n": 0}

    def handler(request):
        appels["n"] += 1
        if appels["n"] == 1:
            return httpx.Response(
                200, json=_mock_tool_call("web_search", {"query": "x"}, "Je cherche d'abord.")
            )
        return httpx.Response(200, json=_mock_texte("Voilà."))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)
    client.cookies.set("filum_session", session_token)
    response = await _post_chat(client, "cherche")
    return next(
        e["payload"]["id"] for e in _lire_evenements(response.text) if e["type"] == "session"
    )


@pytest.mark.asyncio
async def test_la_narration_du_tour_ne_devient_pas_la_reponse(
    client, session_token, db_session, test_user
):
    session_id = await _session_apres_un_tour(client, session_token, db_session, test_user)
    messages = await _messages_persistes(session_id)
    assert [c for r, c in messages if r == "assistant"] == ["Je cherche d'abord.", "Voilà."]


@pytest.mark.asyncio
async def test_un_client_coupe_reprend_le_flux_la_ou_il_l_a_laisse(
    client, session_token, db_session, test_user
):
    session_id = await _session_apres_un_tour(client, session_token, db_session, test_user)
    response = await client.get(f"/api/v1/agent/sessions/{session_id}/flux?depuis=1")
    assert response.status_code == 200
    events = _lire_evenements(response.text)
    assert events[0]["seq"] == 1
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_pas_de_flux_sans_tour(client, session_token, db_session, test_user):
    client.cookies.set("filum_session", session_token)
    response = await client.get(f"/api/v1/agent/sessions/{uuid4()}/flux")
    assert response.status_code == 404
    assert _code_erreur(response) == "aucun_tour"


@pytest.mark.asyncio
async def test_un_second_envoi_pendant_un_tour_est_refuse(
    client, session_token, db_session, test_user
):
    session_id = await _session_apres_un_tour(client, session_token, db_session, test_user)
    tour = agent_tours.reserver(UUID(session_id), test_user.id)
    try:
        lue = await client.get(f"/api/v1/agent/sessions/{session_id}")
        assert lue.json()["tour_en_cours"] is True
        response = await client.post(
            "/api/v1/agent/chat", json={"message": "encore", "session_id": session_id}
        )
        assert response.status_code == 409
        assert _code_erreur(response) == "tour_en_cours"
    finally:
        agent_tours.liberer(tour)
    # Le message refusé n'a pas été inscrit.
    assert [c for r, c in await _messages_persistes(session_id) if r == "user"] == ["cherche"]
    lue = await client.get(f"/api/v1/agent/sessions/{session_id}")
    assert lue.json()["tour_en_cours"] is False


@pytest.mark.asyncio
async def test_arreter_coupe_le_tour_et_garde_ce_qui_est_fait(
    client, session_token, db_session, test_user
):
    await _inserer_provider_defaut(db_session, test_user)

    def handler(request):
        return httpx.Response(200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"}))

    app.dependency_overrides[get_http_client] = lambda: httpx.MockTransport(handler)

    async def jamais(request_id, tool, args):
        await asyncio.Event().wait()
        return False

    app.dependency_overrides[get_approver] = lambda: lambda creator_id: jamais
    client.cookies.set("filum_session", session_token)

    envoi = asyncio.create_task(_post_chat(client, "publie"))
    session_id = None
    for _ in range(200):
        session_id = next(
            (
                sid
                for sid, t in agent_tours._TOURS.items()
                if t.creator_id == test_user.id and not t.termine
            ),
            None,
        )
        if session_id and any(
            e["type"] == "approval_request" for e in agent_tours._TOURS[session_id].evenements
        ):
            break
        await asyncio.sleep(0.02)
    assert session_id is not None

    arret = await client.post(f"/api/v1/agent/sessions/{session_id}/arreter")
    assert arret.status_code == 204
    events = _lire_evenements((await envoi).text)
    assert events[-1]["type"] == "error"
    assert "arrêté" in events[-1]["payload"]["message"]
    # L'appel resté sans réponse est retiré : il rendrait la session inutilisable.
    assert [r for r, _ in await _messages_persistes(str(session_id))] == ["user"]
    assert (await client.post(f"/api/v1/agent/sessions/{session_id}/arreter")).status_code == 404
