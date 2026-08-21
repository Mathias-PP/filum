from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.schemas.agent_provider import (
    PROVIDER_DEFAULT_BASE_URLS,
    AgentProviderCreate,
    ProviderKind,
    _api_key_masked,
)
from app.services import agent_providers as svc
from app.services.agent_providers import AgentProviderError, creer, lister, _classify, _detail_provider
from app.services.agent_providers import tester as service_tester
from app.services.llm import url_chat


class TestMasquage:
    def test_masque_longue(self):
        assert _api_key_masked("sk-abcdefgh1234") == "sk-…1234"

    def test_masque_courte(self):
        assert _api_key_masked("abc") == "…"

    def test_masque_ne_renvoie_jamais_la_cle(self):
        cle = "sk-proj-very-long-secret-9876"
        masque = _api_key_masked(cle)
        assert cle not in masque


class TestResolutionEndpoint:
    def test_racine_nue_prefixe_v1(self):
        assert url_chat("https://api.openai.com") == "https://api.openai.com/v1/chat/completions"

    def test_chemin_present_suffixe_direct(self):
        base = "https://generativelanguage.googleapis.com/v1beta/openai"
        assert url_chat(base) == f"{base}/chat/completions"

    def test_slash_final_ignore(self):
        assert url_chat("https://api.openai.com/") == "https://api.openai.com/v1/chat/completions"


class TestValidationSchema:
    def test_custom_sans_base_url_passe_au_schema(self):
        # Structurellement valide : la base_url exigée pour custom est vérifiée
        # dans le service (elle passe par assert_url_is_safe).
        AgentProviderCreate(
            provider=ProviderKind.CUSTOM, model="m", api_key="k"
        )

    def test_base_url_non_http_refusee(self):
        with pytest.raises(ValidationError):
            AgentProviderCreate(
                provider=ProviderKind.CUSTOM,
                model="m",
                api_key="k",
                base_url="ftp://api.example.com",
            )

    def test_base_url_sans_hote_refusee(self):
        with pytest.raises(ValidationError):
            AgentProviderCreate(
                provider=ProviderKind.CUSTOM,
                model="m",
                api_key="k",
                base_url="https://",
            )

    def test_champ_inconnu_refuse(self):
        with pytest.raises(ValidationError):
            AgentProviderCreate(
                provider=ProviderKind.OPENAI,
                model="m",
                api_key="k",
                spam="oui",
            )

    def test_api_key_vide_apres_strip_refusee(self):
        with pytest.raises(ValidationError):
            AgentProviderCreate(provider=ProviderKind.OPENAI, model="m", api_key="   ")

    def test_base_url_private_ip_valide_au_schema(self):
        # Le contrôle réseau (adresse privée) appartient au service, pas au
        # schéma : le schéma ne fait pas de DNS.
        AgentProviderCreate(
            provider=ProviderKind.CUSTOM,
            model="m",
            api_key="k",
            base_url="http://127.0.0.1:8000",
        )


class TestResolutionBaseUrl:
    def test_defaut_provider_integre(self):
        assert svc._resolve_base_url(ProviderKind.OPENAI, None) == PROVIDER_DEFAULT_BASE_URLS[
            "openai"
        ]

    def test_custom_sans_base_url_refuse(self):
        with pytest.raises(AgentProviderError):
            svc._resolve_base_url(ProviderKind.CUSTOM, None)

    def test_adresse_privee_refusee(self):
        # Adresse IP littérale : vérifiée sans DNS, donc hermétique.
        with pytest.raises(AgentProviderError):
            svc._resolve_base_url(ProviderKind.CUSTOM, "http://127.0.0.1:8000")

    def test_surcharge_d_un_integre_vers_du_prive_refusee(self):
        with pytest.raises(AgentProviderError):
            svc._resolve_base_url(ProviderKind.OPENAI, "http://192.168.1.10:8000")

    def test_custom_valide_resolu(self, monkeypatch):
        # Pas de DNS dans les tests : on neutralise le contrôle réseau.
        monkeypatch.setattr(svc, "assert_url_is_safe", lambda url: None)
        assert svc._resolve_base_url(ProviderKind.CUSTOM, "https://example.com") == (
            "https://example.com"
        )


async def _mk_provider(
    db,
    creator_id,
    *,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com",
    key: str = "sk-test-key-12345678",
    is_default: bool = False,
) -> AgentProvider:
    key_enc = KeyManager(get_settings().master_encryption_key).encrypt_private_key(key)
    p = AgentProvider(
        creator_id=creator_id,
        provider=provider,
        display_name=provider,
        base_url=base_url,
        model=model,
        api_key_enc=key_enc,
        is_default=is_default,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


class TestTester:
    async def test_cle_valide(self, db_session, test_user):
        p = await _mk_provider(db_session, test_user.id)
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is True
        assert result.http_status == 200
        assert result.model_resolved == "gpt-4o-mini"
        assert "Clé valide" in result.message

    async def test_cle_invalide(self, db_session, test_user):
        p = await _mk_provider(db_session, test_user.id)
        transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is False
        assert "Clé API invalide" in result.message

    async def test_quota_epuise(self, db_session, test_user):
        p = await _mk_provider(db_session, test_user.id)
        transport = httpx.MockTransport(lambda request: httpx.Response(429, json={}))

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is False
        assert "crédit" in result.message or "quota" in result.message.lower()

    async def test_modele_inconnu(self, db_session, test_user):
        p = await _mk_provider(db_session, test_user.id)
        transport = httpx.MockTransport(lambda request: httpx.Response(404, json={}))

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is False
        assert "modèle" in result.message.lower() or "provider" in result.message.lower()

    async def test_erreur_reseau(self, db_session, test_user):
        p = await _mk_provider(db_session, test_user.id)

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(boom)

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is False
        assert result.http_status is None
        assert "Impossible de joindre" in result.message

    async def test_anthropic_bascule_sur_messages(self, db_session, test_user):
        p = await _mk_provider(
            db_session,
            test_user.id,
            provider="anthropic",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4",
        )
        vus: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            vus.append(request)
            if request.url.path.endswith("/v1/messages"):
                return httpx.Response(200, json={"content": []})
            return httpx.Response(404, json={})

        transport = httpx.MockTransport(handler)

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is True
        assert len(vus) == 2
        assert vus[0].url.path.endswith("/v1/chat/completions")
        messages_call = vus[1]
        assert messages_call.url.path.endswith("/v1/messages")
        assert messages_call.headers["x-api-key"] == "sk-test-key-12345678"
        assert messages_call.headers["anthropic-version"] == "2023-06-01"

    async def test_provider_d_un_autre_createur_invisible(self, db_session, test_user):
        p = await _mk_provider(db_session, uuid4())
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))

        with pytest.raises(AgentProviderError):
            await service_tester(db_session, test_user.id, p.id, transport=transport)


class TestServiceCrud:
    async def test_creer_et_lister_chiffre(self, db_session, test_user):
        payload = AgentProviderCreate(
            provider=ProviderKind.OPENAI,
            model="gpt-4o-mini",
            api_key="sk-secret-1234",
            is_default=True,
        )
        lu = await creer(db_session, test_user.id, payload)

        assert lu.provider == ProviderKind.OPENAI
        assert lu.base_url == PROVIDER_DEFAULT_BASE_URLS["openai"]
        assert lu.is_default is True
        assert lu.api_key_masked != "sk-secret-1234"

        dans_la_base = await db_session.get(AgentProvider, lu.id)
        assert dans_la_base.api_key_enc != "sk-secret-1234"
        # Le clair n'existe nulle part dans la ligne stockée.
        assert "sk-secret-1234" not in dans_la_base.api_key_enc

        liste = await lister(db_session, test_user.id)
        assert len(liste) == 1
        assert liste[0].api_key_masked == "sk-…1234"

    async def test_un_seul_defaut(self, db_session, test_user):
        premier = await creer(
            db_session,
            test_user.id,
            AgentProviderCreate(
                provider=ProviderKind.OPENAI, model="gpt-4o-mini", api_key="k1", is_default=True
            ),
        )
        second = await creer(
            db_session,
            test_user.id,
            AgentProviderCreate(
                provider=ProviderKind.DEEPSEEK, model="deepseek-chat", api_key="k2", is_default=True
            ),
        )
        liste = await lister(db_session, test_user.id)
        par_id = {p.id: p for p in liste}
        assert par_id[premier.id].is_default is False
        assert par_id[second.id].is_default is True

    async def test_doublon_refuse(self, db_session, test_user):
        payload = AgentProviderCreate(
            provider=ProviderKind.OPENAI, model="gpt-4o-mini", api_key="k"
        )
        await creer(db_session, test_user.id, payload)
        with pytest.raises(AgentProviderError):
            await creer(db_session, test_user.id, payload)


class TestDetailProvider:
    """Le message du provider est la seule information actionnable de la chaine."""

    def test_forme_openai(self):
        r = httpx.Response(429, json={"error": {"message": "You exceeded your current quota."}})
        assert _detail_provider(r) == "You exceeded your current quota."

    def test_forme_liste_gemini(self):
        corps = [
            {
                "error": {
                    "code": 404,
                    "message": "This model models/gemini-2.5-flash is no longer available "
                    "to new users. Please update your code to use models/gemini-3.6-flash.",
                    "status": "NOT_FOUND",
                }
            }
        ]
        assert "gemini-3.6-flash" in (_detail_provider(httpx.Response(404, json=corps)) or "")

    def test_corps_non_json_ne_plante_pas(self):
        r = httpx.Response(502, content=b"<html>Bad Gateway</html>")
        assert "Bad Gateway" in (_detail_provider(r) or "")

    def test_corps_vide_rend_none(self):
        assert _detail_provider(httpx.Response(500, content=b"")) is None


class TestClassifyRemonteLeProvider:
    def test_le_404_gemini_cite_le_modele_de_remplacement(self):
        corps = [{"error": {"code": 404, "message": "use models/gemini-3.6-flash"}}]
        res = _classify("gemini-2.5-flash", "https://x/chat/completions", httpx.Response(404, json=corps))
        assert res.ok is False
        assert "gemini-3.6-flash" in res.message
        assert res.provider_message == "use models/gemini-3.6-flash"

    def test_le_429_openai_dit_le_credit(self):
        r = httpx.Response(429, json={"error": {"message": "insufficient_quota"}})
        res = _classify("gpt-5.6-luna", "https://x/chat/completions", r)
        assert "insufficient_quota" in res.message
        assert "crédit" in res.message or "quota" in res.message.lower()

    def test_succes_inchange(self):
        res = _classify("m", "u", httpx.Response(200, json={}))
        assert res.ok is True
        assert res.provider_message is None
