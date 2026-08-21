"""Tests unitaires de la boucle de l'agent et du registre d'outils."""

from __future__ import annotations

import json

import httpx
import pytest

from app.agent_tools.philum import SENSITIVE_TOOLS, est_sensible
from app.agent_tools.registry import construire_registre, executer
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.services import agent as agent_svc


def _provider(db_session, test_user, *, base_url="https://api.openai.com") -> AgentProvider:
    key = KeyManager(get_settings().master_encryption_key).encrypt_private_key("sk-test-12345678")
    p = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url=base_url,
        model="gpt-4o-mini",
        api_key_enc=key,
        is_default=True,
    )
    db_session.add(p)
    return p


def _mock_texte(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}], "usage": {}}


def _mock_tool_call(name: str, arguments: dict, tool_id: str = "call_1") -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ],
        "usage": {},
    }


async def _collect(db, user, provider, messages, approuver, transport, registre):
    events = []

    async def emit(event):
        events.append(event)

    await agent_svc.boucle(
        db, user, provider, messages, emit, approuver, transport=transport, registre=registre
    )
    return events


def _registre_fake(executed: list) -> dict[str, AgentTool]:
    async def _execute(ctx: ToolContext, args: dict) -> dict:
        executed.append(args)
        return {"ok": True}

    def _outil(name: str) -> AgentTool:
        return AgentTool(
            name=name,
            description=name,
            parameters={"type": "object", "properties": {}, "required": []},
            output="dict",
            execute=_execute,
        )

    return {"publish_card": _outil("publish_card"), "web_search": _outil("web_search")}


class TestSensibilite:
    def test_outils_destructeurs_sensibles(self):
        assert "publish_card" in SENSITIVE_TOOLS
        assert "delete_card" in SENSITIVE_TOOLS
        assert "delete_source" in SENSITIVE_TOOLS
        assert "create_content_attestation" in SENSITIVE_TOOLS
        assert "archive_sources" in SENSITIVE_TOOLS

    def test_verify_excerpts_sensible_seulement_avec_texte_fourni(self):
        assert est_sensible("verify_excerpts", {"source_id": "s"}) is False
        assert (
            est_sensible("verify_excerpts", {"source_id": "s", "provided_text": "un texte"}) is True
        )

    def test_lecture_non_sensible(self):
        assert est_sensible("fs_read", {"path": "AGENTS.md"}) is False
        assert est_sensible("web_search", {"query": "x"}) is False

    def test_update_card_public_est_sensible(self):
        # Publier via `update_card` contourne `publish_card` : même porte.
        assert est_sensible("update_card", {"slug": "f", "visibility": "public"}) is True
        assert est_sensible("update_card", {"slug": "f", "visibility": "private"}) is False
        assert est_sensible("update_card", {"slug": "f", "title": "T"}) is False

    def test_pas_de_sensible_mort(self):
        # Un nom classé sensible mais absent du registre est une garde qui ne
        # garde rien : la liste et les outils exposés doivent rester alignés.
        assert set(construire_registre()) >= SENSITIVE_TOOLS

    def test_tout_outil_irreversible_est_sensible(self):
        # La réciproque : un outil qui publie, détruit, signe ou envoie vers un
        # tiers ne doit jamais s'exécuter sans feu vert humain.
        irreversibles = {
            "publish_card",
            "delete_card",
            "delete_source",
            "delete_excerpt",
            "create_content_attestation",
            "archive_sources",
        }
        registre = construire_registre()
        for nom in irreversibles & set(registre):
            assert est_sensible(nom, {}) is True, f"{nom} exposé mais non sensible"


class TestRegistre:
    def test_registre_contient_les_domaines(self):
        registre = construire_registre()
        noms = set(registre)
        assert {"fs_read", "fs_write", "fs_list"} <= noms
        assert {"create_card", "publish_card", "verify_excerpts"} <= noms
        assert {"search_cards", "get_card"} <= noms
        # fetch_url toujours disponible ; web_search seulement si configure
        # (voir web_tools) — pas de config en tests, donc absent.
        assert "fetch_url" in noms
        assert {"fiche_state", "fiche_etapes"} <= noms

    def test_web_search_absent_sans_configuration(self):
        """web_search non exposé quand pas de provider configuré : évite au
        modèle un tour gâché à essayer un outil qui renvoie systématiquement
        'Recherche web non configurée'."""
        registre = construire_registre()
        assert "web_search" not in registre

    def test_web_search_present_quand_configure(self, monkeypatch):
        from app.agent_tools import web as web_module

        monkeypatch.setattr(web_module.settings, "agent_web_search_provider", "tavily")
        monkeypatch.setattr(web_module.settings, "agent_web_search_api_key", "sk-fake")
        registre = construire_registre()
        assert "web_search" in registre

    def test_tous_les_outils_ont_un_schema_valide(self):
        for outil in construire_registre().values():
            assert outil.parameters["type"] == "object"
            assert "properties" in outil.parameters
            assert all(isinstance(v, dict) for v in outil.parameters["properties"].values())

    @pytest.mark.asyncio
    async def test_executer_outil_inconnu(self, db_session, test_user):
        ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)
        resultat = await executer({}, "nimporte_quoi", {}, ctx)
        assert resultat["error"]

    @pytest.mark.asyncio
    async def test_executer_refuse_le_sensible_sans_approbation(self, db_session, test_user):
        # La garde vit dans `executer`, pas au site d'appel : un orchestrateur
        # qui oublierait l'approbation obtient un refus, pas une publication.
        registre = construire_registre()
        ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)
        resultat = await executer(registre, "publish_card", {"slug": "inexistante"}, ctx)
        assert "validation humaine" in resultat["error"]

    @pytest.mark.asyncio
    async def test_executer_sensible_approuve_atteint_loutil(self, db_session, test_user):
        executed: list[dict] = []
        registre = _registre_fake(executed)
        ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)
        resultat = await executer(
            registre, "publish_card", {"slug": "f"}, ctx, approbation_obtenue=True
        )
        assert resultat == {"ok": True}
        assert executed == [{"slug": "f"}]

    @pytest.mark.asyncio
    async def test_executer_exception_devenue_resultat(self, db_session, test_user):
        async def _boom(ctx, args):
            raise ValueError("explosion contrôlée")

        outil = AgentTool(
            name="boom",
            description="boom",
            parameters={"type": "object", "properties": {}, "required": []},
            output="dict",
            execute=_boom,
        )
        ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)
        resultat = await executer({"boom": outil}, "boom", {}, ctx)
        assert "explosion" in resultat["error"]


class TestBoucle:
    @pytest.mark.asyncio
    async def test_reponse_texte_directe(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=_mock_texte("Bonjour."))
        )
        messages = [{"role": "user", "content": "salut"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        assert [e["type"] for e in events] == ["message_delta", "done"]
        assert events[0]["payload"]["delta"] == "Bonjour."

    @pytest.mark.asyncio
    async def test_outil_puis_texte(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}
        executed = []

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "étoiles"}))
            return httpx.Response(200, json=_mock_texte("J'ai cherché, voici."))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "cherche"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake(executed)
        )
        types = [e["type"] for e in events]
        assert types == ["tool_call", "tool_result", "message_delta", "done"]
        assert executed == [{"query": "étoiles"}]
        assert events[0]["payload"]["name"] == "web_search"
        assert any(m["role"] == "tool" for m in messages)

    @pytest.mark.asyncio
    async def test_reponse_vide_remonte_diagnostic(self, db_session, test_user):
        """Silence interdit : un modèle qui rend un contenu vide sans
        tool_call doit produire un message d'erreur avec finish_reason.
        Cas reel observe sur Gemini 3.7 Flash en prod le 2026-08-21."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": ""},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"completion_tokens": 8192, "prompt_tokens": 42},
                },
            )

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "hello"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        # Un evenement error DOIT etre emis, jamais silence
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert "épuisé" in errors[0]["payload"]["message"].lower() or (
            "epuise" in errors[0]["payload"]["message"].lower()
        )
        assert "gpt-4o-mini" in errors[0]["payload"]["message"]

    @pytest.mark.asyncio
    async def test_reponse_vide_stop_dit_reformuler(self, db_session, test_user):
        """finish_reason=stop avec contenu vide : diagnostic distinct."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": ""},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {},
                },
            )

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "hello"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert "vide" in errors[0]["payload"]["message"].lower()

    @pytest.mark.asyncio
    async def test_429_avec_retry_delay_attend_et_reprend(self, db_session, test_user, monkeypatch):
        """Sur Gemini free tier (5 req/min), un agent qui construit une fiche
        depasse le quota en 5-6 tours. Le provider donne l'attente exacte :
        on retente une fois. Verifie en prod le 2026-08-21."""
        # Neutraliser le vrai sleep pour ne pas ralentir les tests
        attentes: list[float] = []

        async def _fake_sleep(s: float) -> None:
            attentes.append(s)

        monkeypatch.setattr("app.services.agent.asyncio.sleep", _fake_sleep)

        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = [0]

        def handler(request):
            appels[0] += 1
            if appels[0] == 1:
                # Réponse Gemini réelle observée en prod : liste + retryDelay
                return httpx.Response(
                    429,
                    json=[
                        {
                            "error": {
                                "code": 429,
                                "message": "Quota exceeded",
                                "status": "RESOURCE_EXHAUSTED",
                                "details": [
                                    {
                                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                                        "retryDelay": "43s",
                                    }
                                ],
                            }
                        }
                    ],
                )
            return httpx.Response(200, json=_mock_texte("ok apres retry"))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "cherche"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        # Le tour a bien attendu 43s puis réussi
        assert attentes == [43.0]
        types = [e["type"] for e in events]
        assert "message_delta" in types
        assert "error" not in types

    @pytest.mark.asyncio
    async def test_429_sans_retry_delay_rend_message_lisible(self, db_session, test_user):
        """429 sans indication d'attente : message lisible, pas de JSON brut."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return httpx.Response(
                429, json={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}}
            )

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "cherche"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        msg = errors[0]["payload"]["message"]
        assert "quota" in msg.lower() or "débit" in msg.lower() or "debit" in msg.lower()
        assert "Too many requests" in msg
        # Pas de {}/ [ / ' du JSON brut
        assert "{'error'" not in msg

    @pytest.mark.asyncio
    async def test_message_tool_porte_tool_call_id(self, db_session, test_user):
        """Sans ``tool_call_id``, Gemini rejette le tour suivant avec HTTP 400
        INVALID_ARGUMENT. La spec OpenAI l'exige aussi ; OpenAI est juste
        tolérant, Gemini pas. Verifie en prod le 2026-08-21."""
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}
        executed: list[dict] = []

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(
                    200,
                    json=_mock_tool_call("web_search", {"query": "x"}, tool_id="call_abc123"),
                )
            return httpx.Response(200, json=_mock_texte("ok"))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "cherche"}]
        await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake(executed)
        )
        message_tool = next(m for m in messages if m["role"] == "tool")
        assert message_tool.get("tool_call_id") == "call_abc123", (
            "le tool_call_id doit revenir du tool_calls du provider, sinon"
            " Gemini refuse la requête suivante"
        )

    @pytest.mark.asyncio
    async def test_action_sensible_refusee_sans_execution(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}
        executed = []

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(
                    200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"})
                )
            return httpx.Response(200, json=_mock_texte("Publication refusée."))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "publie"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake(executed)
        )
        types = [e["type"] for e in events]
        assert types == [
            "tool_call",
            "approval_request",
            "approval_resolved",
            "tool_result",
            "message_delta",
            "done",
        ]
        assert events[2]["payload"]["approved"] is False
        assert executed == []  # l'outil n'a jamais tourné
        resultat = events[3]["payload"]["result"]
        assert "refusée" in resultat["error"]

    @pytest.mark.asyncio
    async def test_action_sensible_approuvee_execute(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}
        executed = []

        async def approuve(request_id, tool, args):
            return True

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(
                    200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"})
                )
            return httpx.Response(200, json=_mock_texte("Publié."))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "publie"}]
        events = await _collect(
            db_session, test_user, provider, messages, approuve, transport, _registre_fake(executed)
        )
        assert events[2]["payload"]["approved"] is True
        assert executed == [{"slug": "ma-fiche"}]
        assert events[3]["payload"]["result"] == {"ok": True}

    @pytest.mark.asyncio
    async def test_borne_max_tours(self, db_session, test_user, monkeypatch):
        monkeypatch.setattr(agent_svc, "MAX_TOURS", 3)
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "x"}))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "boucle"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        assert events[-1]["type"] == "error"
        assert "3 tours" in events[-1]["payload"]["message"]

    @pytest.mark.asyncio
    async def test_erreur_provider_http(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
        messages = [{"role": "user", "content": "salut"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        assert events[-1]["type"] == "error"
        assert "500" in events[-1]["payload"]["message"]

    @pytest.mark.asyncio
    async def test_retry_backoff_sur_503(self, db_session, test_user, monkeypatch):
        """502/503/504 : backoff [2 s, 5 s], 2 tentatives max. La premiere tentative
        reussit apres 2 s d'attente."""
        attentes: list[float] = []

        async def _fake_sleep(s: float) -> None:
            attentes.append(s)

        monkeypatch.setattr("app.services.agent.asyncio.sleep", _fake_sleep)

        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = [0]

        def handler(request):
            appels[0] += 1
            if appels[0] == 1:
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(200, json=_mock_texte("ok apres 503"))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "hello"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert attentes == [2.0], f"attendait [2.0], obtenu {attentes}"
        types = [e["type"] for e in events]
        assert "message_delta" in types
        assert "error" not in types

    @pytest.mark.asyncio
    async def test_pas_de_retry_sur_401(self, db_session, test_user, monkeypatch):
        """401 ne declenche PAS de retry : c'est un refus definitif, pas un echec
        d'infrastructure."""
        attentes: list[float] = []

        async def _fake_sleep(s: float) -> None:
            attentes.append(s)

        monkeypatch.setattr("app.services.agent.asyncio.sleep", _fake_sleep)

        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = [0]

        def handler(request):
            appels[0] += 1
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "hello"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert appels[0] == 1, "401 ne doit produire qu'un seul appel"
        assert attentes == [], "401 ne doit pas déclencher de sleep"
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert "401" in errors[0]["payload"]["message"]

    @pytest.mark.asyncio
    async def test_appel_anthropic_va_direct_v1_messages(self, db_session, test_user):
        """Pour kind=anthropic, _appel_provider cible /v1/messages directement
        sans passer par /v1/chat/completions."""
        key = KeyManager(get_settings().master_encryption_key).encrypt_private_key(
            "sk-ant-test-key"
        )
        provider = AgentProvider(
            creator_id=test_user.id,
            provider="anthropic",
            display_name="anthropic",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4",
            api_key_enc=key,
            is_default=True,
        )
        db_session.add(provider)
        await db_session.commit()

        vus: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            vus.append(request)
            if request.url.path.endswith("/v1/messages"):
                return httpx.Response(
                    200,
                    json={
                        "content": [{"type": "text", "text": "pong"}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 5, "output_tokens": 2},
                    },
                )
            return httpx.Response(404, json={"error": {"message": "Not found"}})

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "hello"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )

        assert all(req.url.path.endswith("/v1/messages") for req in vus), (
            "Anthropic doit cibler /v1/messages, pas /v1/chat/completions"
        )
        assert vus[0].headers.get("x-api-key") == "sk-ant-test-key"
        assert vus[0].headers.get("anthropic-version") == "2023-06-01"
        types = [e["type"] for e in events]
        assert "done" in types
        assert "error" not in types


async def _refuse(request_id: str, tool: str, args: dict) -> bool:
    return False
