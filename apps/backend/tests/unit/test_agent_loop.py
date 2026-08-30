"""Tests unitaires de la boucle de l'agent et du registre d'outils."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.agent_tools.philum import SENSITIVE_TOOLS, est_sensible
from app.agent_tools.registry import construire_registre, executer
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.models.workspace_file import WorkspaceFile
from app.services import agent as agent_svc
from app.services import agent_sessions


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

    def test_verify_excerpts_non_sensible(self):
        """La verification relit la page : il n'y a rien a faire valider.

        `provided_text` faisait autrefois basculer l'appel en action sensible,
        parce qu'il laissait l'agent attester son propre extrait. Le parametre
        ne lui est plus expose du tout (`_PARAMETRES_MASQUES` dans le catalogue),
        la question ne se pose plus.
        """
        assert est_sensible("verify_excerpts", {"source_id": "s"}) is False

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
    async def test_429_header_retry_after_seconds_reprend(self, db_session, test_user, monkeypatch):
        """429 sans retryDelay Google mais avec le header standard ``Retry-After``
        (OpenAI/Mistral) : on attend le delai du header puis on retente une fois."""
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
                # Pas de retryDelay dans le corps : c'est le header qui porte l'info.
                return httpx.Response(
                    429,
                    headers={"Retry-After": "12"},
                    json={"error": {"message": "Rate limit reached"}},
                )
            return httpx.Response(200, json=_mock_texte("ok apres header retry"))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "cherche"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert attentes == [12.0]
        types = [e["type"] for e in events]
        assert "message_delta" in types
        assert "error" not in types

    @pytest.mark.asyncio
    async def test_extraire_retry_after(self):
        """Le parseur du header ``Retry-After`` supporte secondes et date HTTP."""
        from app.services.agent import _extraire_retry_after

        assert _extraire_retry_after("42") == 42.0
        assert _extraire_retry_after(" 5 ") == 5.0
        # Date HTTP future -> delai positif en secondes
        from datetime import UTC, datetime, timedelta

        future = datetime.now(UTC) + timedelta(seconds=30)
        from email.utils import format_datetime

        delai = _extraire_retry_after(format_datetime(future))
        assert delai is not None and 25.0 <= delai <= 35.0
        # Header absent, illisible ou date passee -> None
        assert _extraire_retry_after(None) is None
        assert _extraire_retry_after("") is None
        assert _extraire_retry_after("pas-un-nombre") is None
        assert _extraire_retry_after("Wed, 21 Oct 2020 07:28:00 GMT") is None

    @pytest.mark.asyncio
    async def test_gemini_thought_signature_preserve_vers_gemini(self, db_session, test_user):
        """Gemini 3.7-flash signe ses tool_calls avec
        `extra_content.google.thought_signature`. Ce champ DOIT revenir dans
        l'historique au tour suivant, sinon Gemini refuse HTTP 400 :
        « Function call is missing a thought_signature ». Bug prod 2026-08-22
        sur le compte de test."""
        provider = AgentProvider(
            creator_id=test_user.id,
            provider="gemini",
            display_name="gemini",
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-3.7-flash",
            api_key_enc=KeyManager(get_settings().master_encryption_key).encrypt_private_key(
                "AQ.test"
            ),
            is_default=True,
        )
        db_session.add(provider)
        await db_session.commit()

        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("Ok."))

        transport = httpx.MockTransport(handler)
        # Historique avec un tool_call Gemini signe
        messages = [
            {"role": "user", "content": "cherche"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_gem_1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": '{"query": "x"}'},
                        "extra_content": {"google": {"thought_signature": "EpoFCpcF..."}},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_gem_1",
                "content": '{"results": []}',
            },
            {"role": "user", "content": "et maintenant ?"},
        ]
        await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        envoyes = corps_recus[0]["messages"]
        assistant = next(m for m in envoyes if m.get("role") == "assistant" and m.get("tool_calls"))
        tc = assistant["tool_calls"][0]
        assert "extra_content" in tc, "sur Gemini, thought_signature doit revenir au tour suivant"
        assert tc["extra_content"]["google"]["thought_signature"] == "EpoFCpcF..."

    @pytest.mark.asyncio
    async def test_thought_signature_retiree_vers_provider_strict(self, db_session, test_user):
        """Sur un provider strict (Mistral), `extra_content` doit disparaitre :
        Mistral refuse 422 `extra_forbidden`. Une session ouverte sur Gemini
        puis continuee sur Mistral doit pouvoir passer."""
        provider = AgentProvider(
            creator_id=test_user.id,
            provider="mistral",
            display_name="mistral",
            base_url="https://api.mistral.ai",
            model="mistral-medium",
            api_key_enc=KeyManager(get_settings().master_encryption_key).encrypt_private_key(
                "sk-test"
            ),
            is_default=True,
        )
        db_session.add(provider)
        await db_session.commit()

        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("Ok."))

        transport = httpx.MockTransport(handler)
        messages = [
            {"role": "user", "content": "x"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": "{}"},
                        "extra_content": {"google": {"thought_signature": "abc"}},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "{}"},
            {"role": "user", "content": "next"},
        ]
        await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        envoyes = corps_recus[0]["messages"]
        assistant = next(m for m in envoyes if m.get("role") == "assistant" and m.get("tool_calls"))
        tc = assistant["tool_calls"][0]
        assert "extra_content" not in tc, (
            "Mistral refuse 422 extra_forbidden si extra_content est present"
        )

    @pytest.mark.asyncio
    async def test_historique_avec_tool_call_orphelin_filtre_avant_envoi(
        self, db_session, test_user
    ):
        """Un tool_call persiste avec un nom d'outil qui n'existe plus (bug SSE
        Gemini d'avant fix, ou hallucination) doit etre filtre de l'historique
        avant envoi, sinon Gemini refuse HTTP 400 « Request contains an
        invalid argument » et l'utilisateur est coince sur cette session pour
        toujours. Bug prod 2026-08-22."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("Reponse."))

        transport = httpx.MockTransport(handler)
        # Historique corrompu : un tool_call inventé + son résultat orphelin
        messages = [
            {"role": "user", "content": "fais une fiche"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_pourri",
                        "type": "function",
                        "function": {
                            "name": "fs_readfs_readfs_readfiche_etapes",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_pourri",
                "content": '{"error": "Outil inconnu."}',
            },
            {"role": "user", "content": "tu peux lire la fiche sur la creatine ?"},
        ]
        await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        envoyes = corps_recus[0]["messages"]
        # Le tool_call pourri et son tool orphelin doivent avoir disparu
        for m in envoyes:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    nom = (tc.get("function") or {}).get("name") or ""
                    assert nom != "fs_readfs_readfs_readfiche_etapes", (
                        "le tool_call pourri est reste dans l'historique envoye"
                    )
            if m.get("role") == "tool":
                assert m.get("tool_call_id") != "call_pourri", (
                    "le message tool orphelin est reste dans l'historique envoye"
                )
        # Les deux messages utilisateur doivent etre presents
        roles = [m["role"] for m in envoyes]
        assert roles.count("user") == 2

    @pytest.mark.asyncio
    async def test_gemini_streaming_tool_calls_sans_index_ne_fusionnent_pas(
        self, db_session, test_user
    ):
        """Gemini fragmente les tool_calls en streaming sans envoyer d'``index``
        et empile plusieurs appels distincts sur la meme position ordinale.
        Sans traitement special, les 4 noms d'outils fusionnaient en un nom
        inexistant (bug prod 2026-08-22 : `fs_readfs_readfs_readfiche_etapes`).
        """
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            # Simule un flux SSE avec 4 tool_calls distincts sans `index`,
            # tous emis dans un seul chunk delta.
            chunks = [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "fs_read",
                                            "arguments": '{"path": "a"}',
                                        }
                                    },
                                    {
                                        "function": {
                                            "name": "fs_read",
                                            "arguments": '{"path": "b"}',
                                        }
                                    },
                                    {
                                        "function": {
                                            "name": "fs_read",
                                            "arguments": '{"path": "c"}',
                                        }
                                    },
                                    {
                                        "function": {
                                            "name": "fiche_etapes",
                                            "arguments": "{}",
                                        }
                                    },
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            ]
            corps = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, content=corps, headers={"content-type": "text/event-stream"})

        # Second appel apres execution : simple texte pour terminer la boucle
        appels = {"n": 0}
        handler_seq = handler

        def handler_multi(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return handler_seq(request)
            return httpx.Response(200, json=_mock_texte("Ok."))

        transport = httpx.MockTransport(handler_multi)
        messages = [{"role": "user", "content": "fais une fiche"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        appels_outils = [e for e in events if e["type"] == "tool_call"]
        noms = [e["payload"]["name"] for e in appels_outils]
        assert noms == ["fs_read", "fs_read", "fs_read", "fiche_etapes"], (
            f"les 4 tool_calls Gemini doivent rester distincts, obtenu : {noms!r}"
        )
        # Aucun nom fusionne ne doit apparaitre
        for nom in noms:
            assert nom in {"fs_read", "fiche_etapes"}, f"nom fusionne detecte : {nom!r}"

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
    async def test_historique_pollue_gemini_assaini_avant_envoi(self, db_session, test_user):
        """Gemini signe ses tool_calls d'un ``extra_content.google.thought_signature``
        ; l'ancien code copiait le message du provider verbatim dans l'historique
        persiste. Rejouer cette historique vers un provider strict (Mistral)
        repondait 422 ``extra_forbidden`` des le tour suivant. Verifie en prod
        le 2026-08-21."""
        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            if len(corps_recus) == 1:
                return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "x"}))
            return httpx.Response(200, json=_mock_texte("ok"))

        transport = httpx.MockTransport(handler)
        messages = [
            {"role": "user", "content": "cherche"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_old",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": '{"query": "x"}'},
                        "extra_content": {"google": {"thought_signature": "EpoFCpcF"}},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_old",
                "content": "{}",
                "champ_etranger": 1,
            },
            {"role": "user", "content": "et maintenant ?"},
        ]
        await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        envoyes = corps_recus[0]["messages"]
        assistant = next(m for m in envoyes if m.get("role") == "assistant")
        tc = assistant["tool_calls"][0]
        assert set(tc) == {"id", "type", "function"}, (
            "un tool_call specifique Gemini ne doit jamais repartir tel quel"
        )
        tool_msg = next(m for m in envoyes if m["role"] == "tool")
        assert "champ_etranger" not in tool_msg

    @pytest.mark.asyncio
    async def test_approval_request_contient_resume_lisible(self, db_session, test_user):
        """L'événement approval_request porte une phrase lisible qui résout le
        slug/UUID en titre réel. Sans ça, l'utilisateur voit un JSON opaque et
        l'approbation devient un chèque en blanc."""
        from app.models.biblio_card import BiblioCard, CardStatus
        from app.schemas.biblio_card import ContentType, Platform

        card = BiblioCard(
            user_id=test_user.id,
            slug="ma-fiche",
            title="Les mitochondries expliquées",
            platform=Platform.BLOG,
            content_type=ContentType.ARTICLE,
            status=CardStatus.DRAFT,
        )
        db_session.add(card)
        provider = _provider(db_session, test_user)
        await db_session.commit()

        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(
                    200, json=_mock_tool_call("publish_card", {"slug": "ma-fiche"})
                )
            return httpx.Response(200, json=_mock_texte("ok."))

        transport = httpx.MockTransport(handler)
        messages = [{"role": "user", "content": "publie"}]
        events = await _collect(
            db_session, test_user, provider, messages, _refuse, transport, _registre_fake([])
        )
        demandes = [e for e in events if e["type"] == "approval_request"]
        assert len(demandes) == 1
        payload = demandes[0]["payload"]
        assert "resume" in payload, "l'événement doit porter un résumé lisible"
        resume = payload["resume"]
        assert "Les mitochondries" in resume, (
            f"le résumé doit citer le titre réel de la fiche, pas le slug ; obtenu : {resume!r}"
        )
        assert "aucune source" in resume, (
            "publier une fiche vide doit se voir avant, pas se découvrir en ligne ; "
            f"obtenu : {resume!r}"
        )

    @pytest.mark.asyncio
    async def test_resume_de_publication_dit_l_etat_reel(self, db_session, test_user):
        """« Publier la fiche X ? » n'apprend rien : le titre, l'utilisateur le connaît.

        Ce qu'il ne connaît pas, c'est ce que l'agent vient de construire. Le
        résumé compte les sources et distingue les extraits retrouvés dans leur
        page de ceux qui ne l'ont pas été.
        """
        from app.models.biblio_card import BiblioCard, CardStatus
        from app.models.source import Source
        from app.models.source_excerpt import SourceExcerpt
        from app.schemas.biblio_card import ContentType, Platform
        from app.services.agent import _etat_avant_publication

        card = BiblioCard(
            user_id=test_user.id,
            slug="fiche-garnie",
            title="Sommeil et mémoire",
            platform=Platform.BLOG,
            content_type=ContentType.ARTICLE,
            status=CardStatus.DRAFT,
        )
        db_session.add(card)
        await db_session.flush()
        source = Source(
            biblio_card_id=card.id,
            position=1,
            url="https://example.org/a",
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
        )
        db_session.add(source)
        await db_session.flush()
        db_session.add_all(
            [
                SourceExcerpt(
                    source_id=source.id, position=1, text="retrouvé", verified_status="found"
                ),
                SourceExcerpt(
                    source_id=source.id,
                    position=2,
                    text="page muette",
                    verified_status="unreadable",
                ),
            ]
        )
        await db_session.commit()

        resume = await _etat_avant_publication(db_session, test_user, "fiche-garnie")
        assert "Sommeil et mémoire" in resume
        assert "1 source" in resume
        assert "2 extraits dont 1 retrouvé" in resume

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
        assert events[-1]["type"] == "continuation"
        assert "3" in events[-1]["payload"]["message"]
        assert events[-1]["payload"]["tours"] == 3

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
        # Jitter ±25 % autour de la base [2 s] : verifie le rang plutot que la
        # valeur exacte.
        assert len(attentes) == 1
        assert 1.5 <= attentes[0] <= 2.5, f"attente hors jitter ±25% : {attentes}"
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


@pytest.mark.asyncio
class TestUsagePersistance:
    async def test_ajouter_message_persiste_usage(self, db_session, test_user):
        """ajouter_message() persiste prompt_tokens et completion_tokens."""
        session = await agent_sessions.creer(db_session, test_user.id, title="test")
        await agent_sessions.ajouter_message(
            db_session,
            session,
            role="assistant",
            content="pong",
            prompt_tokens=10,
            completion_tokens=5,
        )

        msgs = await agent_sessions.messages(db_session, test_user.id, session.id)
        msg = msgs[0]
        assert msg.prompt_tokens == 10
        assert msg.completion_tokens == 5

    async def test_usage_agrege_par_session(self, db_session, test_user):
        """usage_session() renvoie la somme des tokens de tous les messages."""
        session = await agent_sessions.creer(db_session, test_user.id, title="test")
        await agent_sessions.ajouter_message(db_session, session, role="user", content="hello")
        await agent_sessions.ajouter_message(
            db_session,
            session,
            role="assistant",
            content="tour 1",
            prompt_tokens=100,
            completion_tokens=20,
        )
        await agent_sessions.ajouter_message(
            db_session,
            session,
            role="assistant",
            content="tour 2",
            prompt_tokens=120,
            completion_tokens=30,
        )

        usage = await agent_sessions.usage_session(db_session, test_user.id, session.id)
        assert usage["total_prompt_tokens"] == 220
        assert usage["total_completion_tokens"] == 50
        assert usage["cost_eur"] is None

    async def test_done_event_inclut_usage(self, db_session, test_user):
        """boucle() inclut usage dans l'evenement done."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 42, "completion_tokens": 7},
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

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        u = done_events[0]["payload"].get("usage")
        assert isinstance(u, dict)
        assert u["prompt_tokens"] == 42
        assert u["completion_tokens"] == 7


@pytest.mark.asyncio
class TestPrimingWorkspace:
    async def test_vide_si_pas_de_fichiers(self, db_session, test_user):
        """Sans fichiers shared/ en base, le priming renvoie une chaine vide."""
        ctx = await agent_svc._priming_workspace(db_session, test_user.id)
        assert ctx == ""

    async def test_injecte_les_shared(self, db_session, test_user):
        """Avec des fichiers shared/, le priming les inclut dans la sortie."""
        from hashlib import sha256

        contenu = "Ne jamais fabriquer de source."
        sha = sha256(contenu.encode()).hexdigest()
        db_session.add(
            WorkspaceFile(
                creator_id=test_user.id,
                path="shared/garde-fous.md",
                content=contenu,
                sha256=sha,
            )
        )
        await db_session.commit()

        ctx = await agent_svc._priming_workspace(db_session, test_user.id)
        assert "shared/garde-fous.md" in ctx
        assert "Ne jamais fabriquer de source." in ctx

    async def test_respecte_la_limite(self, db_session, test_user):
        """Les fichiers trop volumineux ne font pas exploser le prompt."""
        from hashlib import sha256

        gros = "x" * (agent_svc._PRIMING_MAX + 1000)
        sha = sha256(gros.encode()).hexdigest()
        db_session.add(
            WorkspaceFile(
                creator_id=test_user.id,
                path="shared/gros.md",
                content=gros,
                sha256=sha,
            )
        )
        await db_session.commit()

        ctx = await agent_svc._priming_workspace(db_session, test_user.id)
        assert len(ctx) <= agent_svc._PRIMING_MAX

    async def test_boucle_injecte_workspace_dans_systeme(self, db_session, test_user):
        """boucle() doit inserer le contexte workspace dans le message system."""
        from hashlib import sha256

        contenu = "Principe editorial de test."
        sha = sha256(contenu.encode()).hexdigest()
        db_session.add(
            WorkspaceFile(
                creator_id=test_user.id,
                path="shared/principes.md",
                content=contenu,
                sha256=sha,
            )
        )
        await db_session.commit()

        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("ok"))

        messages = [{"role": "user", "content": "test"}]
        await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        system_msg = next(m for m in corps_recus[0]["messages"] if m["role"] == "system")
        assert "Principe editorial de test." in system_msg["content"]


class TestDateDuJour:
    """Le prompt systeme doit dire au modele quel jour on est.

    `_SYSTEME` interdit de fabriquer une date de memoire, et aucune date
    n'etait donnee au modele : il datait donc au petit bonheur de son cutoff
    d'entrainement. Sur un produit dont l'argument est de ne rien inventer,
    c'est la contradiction la moins chere a lever.
    """

    async def test_la_date_du_jour_est_dans_le_prompt(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps_recus: list[dict] = []

        def handler(request):
            corps_recus.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("ok"))

        await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "test"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        systeme = next(m for m in corps_recus[0]["messages"] if m["role"] == "system")
        assert datetime.now(UTC).date().isoformat() in systeme["content"]

    def test_la_date_est_calculee_a_l_appel_pas_au_chargement(self):
        """Un processus qui vit plusieurs jours servait sinon une date perimee."""
        veille = agent_svc._contexte_temporel(datetime(2026, 8, 29, 10, 0, tzinfo=UTC))
        jour = agent_svc._contexte_temporel(datetime(2026, 8, 30, 10, 0, tzinfo=UTC))
        assert "2026-08-29" in veille
        assert "2026-08-30" in jour
        assert veille != jour

    def test_le_contexte_temporel_interdit_la_date_de_memoire(self):
        texte = agent_svc._contexte_temporel(datetime(2026, 8, 30, tzinfo=UTC))
        assert "mémoire" in texte or "memoire" in texte


class TestSystemeAgent:
    def test_regles_absolues_dans_systeme(self):
        """Le prompt systeme doit contenir les regles absolues."""
        assert "Agis, ne planifie pas" in agent_svc._SYSTEME
        assert "Ne fabrique jamais" in agent_svc._SYSTEME
        assert "verbatim" in agent_svc._SYSTEME
        assert "corrige avant de supprimer" in agent_svc._SYSTEME

    @pytest.mark.asyncio
    async def test_web_search_non_configure_interdit_fabrication(self):
        """Le refus nomme l'issue, et dit que combler de memoire serait vain.

        Interdire ne suffit pas : un modele prive d'outil comble. Le message
        renvoie donc au createur, et rappelle que `add_source` joint l'adresse
        avant d'ecrire, ce qui rend le comblement sans effet.
        """
        from app.agent_tools.tool import ToolContext
        from app.agent_tools.web import _execute_web_search

        ctx = ToolContext(db=None, user=None, creator_id=None)
        result = await _execute_web_search(ctx, {"query": "test"})
        assert "de mémoire" in result["error"]
        assert "créateur" in result["error"]
        assert "add_source" in result["error"]


@pytest.mark.asyncio
class TestAgentNomme:
    """Un agent nomme restreint les outils envoyes et le contexte injecte."""

    @staticmethod
    def _definition(**kwargs):
        from app.services.agent_definitions import AgentDefinition

        defauts = dict(
            slug="publicateur",
            name="Publicateur",
            contract="Publie une fiche prete.",
            system_prompt="Tu publies, tu ne rediges pas.",
            tools=("publish_card",),
            context=(),
        )
        defauts.update(kwargs)
        return AgentDefinition(**defauts)

    async def _corps_envoye(self, db_session, test_user, agent_def):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps: list[dict] = []

        def handler(request):
            corps.append(json.loads(request.content))
            return httpx.Response(200, json=_mock_texte("ok"))

        events = []

        async def emit(event):
            events.append(event)

        await agent_svc.boucle(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "vas-y"}],
            emit,
            _refuse,
            transport=httpx.MockTransport(handler),
            registre=_registre_fake([]),
            agent_def=agent_def,
        )
        return corps[0]

    async def test_seuls_les_outils_de_l_agent_sont_envoyes(self, db_session, test_user):
        corps = await self._corps_envoye(db_session, test_user, self._definition())
        noms = {o["function"]["name"] for o in corps["tools"]}
        assert noms == {"publish_card"}

    async def test_le_prompt_systeme_porte_le_role(self, db_session, test_user):
        corps = await self._corps_envoye(db_session, test_user, self._definition())
        systeme = next(m for m in corps["messages"] if m["role"] == "system")
        # Le prompt general reste : le role s'ajoute, il ne remplace pas.
        assert "Agis, ne planifie pas" in systeme["content"]
        assert "Publicateur" in systeme["content"]
        assert "Tu publies, tu ne rediges pas." in systeme["content"]

    async def test_le_contexte_se_limite_aux_fichiers_nommes(self, db_session, test_user):
        from hashlib import sha256

        for chemin, contenu in (
            ("shared/garde-fous.md", "Le garde-fou attendu."),
            ("shared/style-redactionnel.md", "Le style non demande."),
        ):
            db_session.add(
                WorkspaceFile(
                    creator_id=test_user.id,
                    path=chemin,
                    content=contenu,
                    sha256=sha256(contenu.encode()).hexdigest(),
                )
            )
        await db_session.commit()

        corps = await self._corps_envoye(
            db_session, test_user, self._definition(context=("shared/garde-fous.md",))
        )
        systeme = next(m for m in corps["messages"] if m["role"] == "system")
        assert "Le garde-fou attendu." in systeme["content"]
        assert "Le style non demande." not in systeme["content"]

    async def test_agent_sans_contexte_n_injecte_rien(self, db_session, test_user):
        from hashlib import sha256

        contenu = "Le style non demande."
        db_session.add(
            WorkspaceFile(
                creator_id=test_user.id,
                path="shared/style-redactionnel.md",
                content=contenu,
                sha256=sha256(contenu.encode()).hexdigest(),
            )
        )
        await db_session.commit()

        corps = await self._corps_envoye(db_session, test_user, self._definition())
        systeme = next(m for m in corps["messages"] if m["role"] == "system")
        assert contenu not in systeme["content"]


class TestArgumentsTronques:
    """Un appel d'outil aux arguments illisibles ne doit pas s'exécuter.

    Un flux coupé au milieu du JSON laissait des arguments tronqués, lus comme
    ``{}``. L'outil partait quand même, et le modèle rapportait comme fait un
    appel qu'il n'avait pas formulé.
    """

    @staticmethod
    def _mock_arguments(brut: str) -> dict:
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
                                "function": {"name": "web_search", "arguments": brut},
                            }
                        ],
                    }
                }
            ],
            "usage": {},
        }

    @pytest.mark.asyncio
    async def test_un_json_tronque_n_execute_pas_l_outil(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        executed: list = []
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=self._mock_arguments('{"query": "éto'))
            return httpx.Response(200, json=_mock_texte("Je refais."))

        messages = [{"role": "user", "content": "cherche"}]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake(executed),
        )
        assert executed == []
        resultat = next(e for e in events if e["type"] == "tool_result")
        assert "illisibles" in resultat["payload"]["result"]["error"]

    @pytest.mark.asyncio
    async def test_le_modele_recoit_une_reponse_pour_son_appel(self, db_session, test_user):
        # Un tool_call sans message tool en face fait rejeter le tour suivant
        # par tous les fournisseurs : le refus doit répondre, pas se taire.
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=self._mock_arguments("{oops"))
            return httpx.Response(200, json=_mock_texte("Je refais."))

        messages = [{"role": "user", "content": "cherche"}]
        await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        outils = [m for m in messages if m["role"] == "tool"]
        assert len(outils) == 1
        assert outils[0]["tool_call_id"] == "call_1"

    @pytest.mark.asyncio
    async def test_des_arguments_vides_restent_valides(self, db_session, test_user):
        # Un outil sans paramètre est appelé avec "" ou "{}" : absent n'est pas
        # malformé.
        provider = _provider(db_session, test_user)
        await db_session.commit()
        executed: list = []
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=self._mock_arguments(""))
            return httpx.Response(200, json=_mock_texte("Fait."))

        await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "cherche"}],
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake(executed),
        )
        assert executed == [{}]


class TestCompactionContexte:
    """Une session longue ne doit pas mourir sur la fenêtre du modèle.

    Deux filets : un budget préventif appliqué avant l'appel, et un rejeu
    unique quand le fournisseur refuse quand même. Le second existe parce que
    le premier est un pari : on ne connaît pas la fenêtre réelle du modèle.
    """

    @staticmethod
    def _refus_contexte() -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": (
                        "This model's maximum context length is 8192 tokens. "
                        "However, your messages resulted in 20000 tokens."
                    ),
                    "code": "context_length_exceeded",
                }
            },
        )

    @pytest.mark.asyncio
    async def test_rejeu_unique_apres_un_refus_du_fournisseur(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            # Un 400 coûte deux appels : le stream refusé, puis le repli bloquant.
            if appels["n"] <= 2:
                return TestCompactionContexte._refus_contexte()
            return httpx.Response(200, json=_mock_texte("Voilà."))

        messages = [{"role": "user", "content": f"{i}:" + "u" * 1_000} for i in range(40)]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        types = [e["type"] for e in events]
        assert "contexte_compacte" in types
        assert "error" not in types
        assert types[-1] == "done"

    @pytest.mark.asyncio
    async def test_un_second_refus_remonte_l_erreur(self, db_session, test_user):
        """Deux refus de suite ne viennent plus de la taille : ne pas boucler."""
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return TestCompactionContexte._refus_contexte()

        messages = [{"role": "user", "content": f"{i}:" + "u" * 1_000} for i in range(40)]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert [e["type"] for e in events].count("contexte_compacte") == 1
        assert events[-1]["type"] == "error"

    @pytest.mark.asyncio
    async def test_une_erreur_ordinaire_ne_declenche_rien(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()

        def handler(request):
            return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

        messages = [{"role": "user", "content": "bonjour"}]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert [e["type"] for e in events] == ["error"]

    @pytest.mark.asyncio
    async def test_compaction_preventive_avant_le_premier_appel(self, db_session, test_user):
        """Au-dessus du budget, on coupe avant d'envoyer, pas après le refus."""
        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps = {}

        def handler(request):
            corps["envoye"] = json.loads(request.content)
            return httpx.Response(200, json=_mock_texte("Voilà."))

        gros = "u" * 2_000
        messages = [{"role": "user", "content": f"{i}:{gros}"} for i in range(250)]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        assert [e["type"] for e in events][0] == "contexte_compacte"
        envoyes = corps["envoye"]["messages"]
        assert len(envoyes) < 251
        assert agent_sessions.taille_historique(envoyes) <= agent_sessions.BUDGET_HISTORIQUE
        assert envoyes[-1]["content"].startswith("249:")

    @pytest.mark.asyncio
    async def test_l_ancre_du_tour_precedent_declenche_la_compaction(self, db_session, test_user):
        """Le compte réel du fournisseur fait autorité dès le premier appel.

        Un historique que l'estimation croit sous le budget mais que le
        fournisseur a déjà compté quatre fois plus gros doit être coupé avant
        l'envoi, pas après un refus.
        """
        provider = _provider(db_session, test_user)
        await db_session.commit()
        corps = {}

        def handler(request):
            corps["envoye"] = json.loads(request.content)
            return httpx.Response(200, json=_mock_texte("Voilà."))

        messages = [{"role": "user", "content": f"{i}:{'u' * 2_000}"} for i in range(30)]
        events = []

        async def emit(event):
            events.append(event)

        await agent_svc.boucle(
            db_session,
            test_user,
            provider,
            messages,
            emit,
            _refuse,
            transport=httpx.MockTransport(handler),
            registre=_registre_fake([]),
            ancre_tokens=(len(messages), agent_sessions.BUDGET_HISTORIQUE * 4),
        )
        assert [e["type"] for e in events][0] == "contexte_compacte"
        assert len(corps["envoye"]["messages"]) < 31

    @pytest.mark.asyncio
    async def test_la_passe_preventive_ne_consomme_pas_le_rejeu(self, db_session, test_user):
        """Compacter au départ ne doit pas priver du rattrapage sur refus.

        Les deux filets sont indépendants : le budget préventif est une
        estimation, le refus du fournisseur est un fait.
        """
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] <= 2:
                return TestCompactionContexte._refus_contexte()
            return httpx.Response(200, json=_mock_texte("Voilà."))

        gros = "u" * 2_000
        messages = [{"role": "user", "content": f"{i}:{gros}"} for i in range(250)]
        events = await _collect(
            db_session,
            test_user,
            provider,
            messages,
            _refuse,
            httpx.MockTransport(handler),
            _registre_fake([]),
        )
        types = [e["type"] for e in events]
        assert types.count("contexte_compacte") == 2
        assert types[-1] == "done"


class TestControleRelance:
    """Le tour final annonce une action que rien dans le tour n'a exécutée.

    Vu en production : le modèle écrit « j'ai ajouté la source » sans avoir
    jamais appelé l'outil. La règle 1 du prompt système l'interdit déjà, et ne
    suffit pas ; ce contrôle est la même exigence, mais vérifiée par le code.
    """

    def _registre_ecriture(self, executed: list) -> dict[str, AgentTool]:
        async def _execute(ctx: ToolContext, args: dict) -> dict:
            executed.append(args)
            return {"ok": True}

        return {
            "create_card": AgentTool(
                name="create_card",
                description="create_card",
                parameters={"type": "object", "properties": {}, "required": []},
                output="dict",
                execute=_execute,
            ),
            "web_search": AgentTool(
                name="web_search",
                description="web_search",
                parameters={"type": "object", "properties": {}, "required": []},
                output="dict",
                execute=_execute,
            ),
        }

    @pytest.mark.asyncio
    async def test_annonce_sans_ecriture_relance_une_fois(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=_mock_texte("J'ai créé la fiche, c'est prêt."))
            return httpx.Response(200, json=_mock_texte("Rien n'a été créé, je m'en excuse."))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "crée une fiche"}],
            _refuse,
            httpx.MockTransport(handler),
            self._registre_ecriture([]),
        )
        types = [e["type"] for e in events]
        assert types.count("controle_relance") == 1
        assert types[-1] == "done"
        assert appels["n"] == 2

    @pytest.mark.asyncio
    async def test_une_seule_relance_meme_si_le_modele_persiste(self, db_session, test_user):
        # Sans ce plafond, un modèle qui répète son annonce brûlerait le quota
        # de tours entier en relances.
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            return httpx.Response(200, json=_mock_texte("J'ai ajouté la source."))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "ajoute"}],
            _refuse,
            httpx.MockTransport(handler),
            self._registre_ecriture([]),
        )
        assert [e["type"] for e in events].count("controle_relance") == 1
        assert appels["n"] == 2

    @pytest.mark.asyncio
    async def test_une_ecriture_reelle_ne_declenche_rien(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}
        executed: list = []

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=_mock_tool_call("create_card", {"title": "T"}))
            return httpx.Response(200, json=_mock_texte("J'ai créé la fiche."))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "crée"}],
            _refuse,
            httpx.MockTransport(handler),
            self._registre_ecriture(executed),
        )
        assert "controle_relance" not in [e["type"] for e in events]
        assert executed == [{"title": "T"}]

    @pytest.mark.asyncio
    async def test_une_lecture_seule_ne_vaut_pas_ecriture(self, db_session, test_user):
        # `web_search` prouve que le modèle a travaillé, pas qu'il a écrit.
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            if appels["n"] == 1:
                return httpx.Response(200, json=_mock_tool_call("web_search", {"query": "x"}))
            if appels["n"] == 2:
                return httpx.Response(200, json=_mock_texte("J'ai enregistré la source."))
            return httpx.Response(200, json=_mock_texte("Je n'ai rien enregistré."))

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "cherche puis ajoute"}],
            _refuse,
            httpx.MockTransport(handler),
            self._registre_ecriture([]),
        )
        assert [e["type"] for e in events].count("controle_relance") == 1

    @pytest.mark.asyncio
    async def test_une_reponse_sans_annonce_passe_directement(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()
        appels = {"n": 0}

        def handler(request):
            appels["n"] += 1
            return httpx.Response(
                200, json=_mock_texte("Je vais créer la fiche. Quel titre veux-tu ?")
            )

        events = await _collect(
            db_session,
            test_user,
            provider,
            [{"role": "user", "content": "salut"}],
            _refuse,
            httpx.MockTransport(handler),
            self._registre_ecriture([]),
        )
        assert "controle_relance" not in [e["type"] for e in events]
        assert appels["n"] == 1

    def test_la_negation_n_est_pas_une_annonce(self):
        # Le motif doit laisser passer l'aveu, sinon le contrôle punirait
        # exactement la réponse honnête qu'il cherche à obtenir.
        for texte in (
            "Je n'ai pas créé la fiche : la source est illisible.",
            "Je n'ai rien ajouté, l'URL est morte.",
            "Il faudra créer la fiche ensuite.",
        ):
            assert agent_svc._ANNONCE_FAITE.search(texte) is None, texte

    def test_les_outils_qui_ecrivent_sont_tous_exposes(self):
        # Un nom mal orthographié ici rendrait le contrôle aveugle en silence.
        from app.agent_tools.philum import OUTILS_QUI_ECRIVENT

        assert OUTILS_QUI_ECRIVENT <= set(construire_registre())
