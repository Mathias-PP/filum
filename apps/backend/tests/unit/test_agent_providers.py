from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.schemas.agent_provider import (
    MODELES_SUGGERES,
    PROVIDER_DEFAULT_BASE_URLS,
    AgentProviderCreate,
    ProviderKind,
    _api_key_masked,
)
from app.services import agent_providers as svc
from app.services.agent_providers import (
    AgentProviderError,
    _classify,
    _detail_provider,
    creer,
    lister,
    lister_modeles,
)
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
        AgentProviderCreate(provider=ProviderKind.CUSTOM, model="m", api_key="k")

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
        assert (
            svc._resolve_base_url(ProviderKind.OPENAI, None) == PROVIDER_DEFAULT_BASE_URLS["openai"]
        )

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
        monkeypatch.setattr(svc, "assert_url_is_safe", lambda url, **_: None)
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

    async def test_anthropic_va_direct_en_messages(self, db_session, test_user):
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
            if request.url.path.endswith("/models"):
                # Le succes du test declenche un auto-fetch des modeles (chauffe
                # le cache). Anthropic ne sert pas /models en OpenAI-compat :
                # 404, repli sur MODELES_SUGGERES silencieusement.
                return httpx.Response(404, json={})
            return httpx.Response(404, json={})

        transport = httpx.MockTransport(handler)

        result = await service_tester(db_session, test_user.id, p.id, transport=transport)

        assert result.ok is True
        # 2 requetes : (1) messages direct, (2) auto-fetch models pour chauffer le cache
        assert len(vus) == 2
        messages_call = vus[0]
        assert messages_call.url.path.endswith("/v1/messages")
        assert messages_call.headers["x-api-key"] == "sk-test-key-12345678"
        assert messages_call.headers["anthropic-version"] == "2023-06-01"
        assert vus[1].url.path.endswith("/models")

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

    def test_forme_mistral_detail(self):
        """Mistral rend {"detail": "..."} (convention FastAPI/pydantic)."""
        r = httpx.Response(401, json={"detail": "Invalid API Key"})
        assert _detail_provider(r) == "Invalid API Key"

    def test_forme_cerebras_message_racine(self):
        """Cerebras rend {"message": "...", "type": "...", "code": "..."} sans wrapper error."""
        r = httpx.Response(
            401,
            json={
                "message": "Wrong API Key",
                "type": "invalid_request_error",
                "param": "api_key",
                "code": "wrong_api_key",
            },
        )
        assert _detail_provider(r) == "Wrong API Key"


class TestClassifyParCodeErreur:
    """Le code d'erreur du provider dit plus precisement que le status HTTP.

    Sans cette distinction, HTTP 429 est toujours "credit ou quota ou debit",
    et l'utilisateur ne sait pas quoi faire : recharger, attendre, ou changer de
    modele.
    """

    def test_insufficient_quota_dit_credit_epuise(self):
        r = httpx.Response(
            429, json={"error": {"code": "insufficient_quota", "message": "You exceeded"}}
        )
        res = _classify("m", "u", r)
        assert "crédit" in res.message.lower() or "credit" in res.message.lower()
        assert "épuisé" in res.message.lower() or "epuise" in res.message.lower()

    def test_rate_limit_exceeded_dit_reessayer(self):
        r = httpx.Response(
            429, json={"error": {"code": "rate_limit_exceeded", "message": "Rate limit"}}
        )
        res = _classify("m", "u", r)
        assert "débit" in res.message.lower() or "debit" in res.message.lower()
        assert "réessayer" in res.message.lower() or "reessayer" in res.message.lower()

    def test_invalid_api_key_dit_cle_revoquee(self):
        r = httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "bad key"}})
        res = _classify("m", "u", r)
        assert "clé" in res.message.lower() or "cle" in res.message.lower()
        assert "révoquée" in res.message.lower() or "revoquee" in res.message.lower()

    def test_model_not_found(self):
        r = httpx.Response(
            404, json={"error": {"code": "model_not_found", "message": "no such model"}}
        )
        res = _classify("gpt-inconnu", "u", r)
        assert "modèle" in res.message.lower() or "modele" in res.message.lower()

    def test_context_length_exceeded(self):
        r = httpx.Response(
            400, json={"error": {"code": "context_length_exceeded", "message": "too long"}}
        )
        res = _classify("m", "u", r)
        assert "conversation" in res.message.lower() or "contexte" in res.message.lower()

    def test_code_cerebras_racine(self):
        """Cerebras met code a la racine, pas dans error.code."""
        r = httpx.Response(
            401,
            json={
                "message": "Wrong API Key",
                "code": "wrong_api_key",
                "type": "invalid_request_error",
            },
        )
        res = _classify("m", "u", r)
        assert "clé" in res.message.lower() or "cle" in res.message.lower()

    def test_code_inconnu_retombe_sur_le_status(self):
        """Un code non repertorie doit retomber sur le cadrage HTTP, pas planter."""
        r = httpx.Response(403, json={"error": {"code": "some_new_code", "message": "hmm"}})
        res = _classify("m", "u", r)
        # Retombe sur _CADRAGES[403]
        assert "refusé" in res.message.lower() or "refuse" in res.message.lower()
        # Le message brut du provider apparait tout de meme
        assert "hmm" in res.message


class TestClassifyRemonteLeProvider:
    def test_le_404_gemini_cite_le_modele_de_remplacement(self):
        corps = [{"error": {"code": 404, "message": "use models/gemini-3.6-flash"}}]
        res = _classify(
            "gemini-2.5-flash", "https://x/chat/completions", httpx.Response(404, json=corps)
        )
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


@pytest.mark.asyncio
class TestListerModeles:
    async def test_rend_la_liste_du_provider(self, db_session, test_user):
        provider = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/models")
            return httpx.Response(
                200,
                json={"data": [{"id": "gpt-5.6-terra"}, {"id": "gpt-5.6-luna"}]},
            )

        res = await lister_modeles(
            db_session, test_user.id, provider.id, transport=httpx.MockTransport(handler)
        )

        assert res["source"] == "provider"
        assert res["models"] == ["gpt-5.6-luna", "gpt-5.6-terra"]

    async def test_replie_sur_la_liste_curee_si_le_provider_refuse(self, db_session, test_user):
        provider = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        res = await lister_modeles(
            db_session, test_user.id, provider.id, transport=httpx.MockTransport(handler)
        )

        assert res["source"] == "repli"
        assert res["models"] == MODELES_SUGGERES["openai"]
        assert "bad key" in res["message"]

    async def test_ne_leve_pas_sur_une_panne_reseau(self, db_session, test_user):
        provider = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("injoignable")

        res = await lister_modeles(
            db_session, test_user.id, provider.id, transport=httpx.MockTransport(handler)
        )
        assert res["source"] == "repli"


class TestCacheModeles:
    """Le sélecteur de modèle rappelle /models à chaque ouverture.

    Un cache 15 min par (créateur, provider) rend le dropdown instantané et
    évite de brûler du rate-limit chez le fournisseur pour une info qui bouge
    rarement à l'échelle d'un compte utilisateur.
    """

    async def test_deuxieme_appel_ne_touche_pas_le_reseau(self, db_session, test_user):
        # Isoler du cache global : purger avant le test
        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)
        appels: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            appels.append(str(request.url))
            return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

        transport = httpx.MockTransport(handler)
        r1 = await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        r2 = await lister_modeles(db_session, test_user.id, provider.id, transport=transport)

        assert r1 == r2
        assert r1["source"] == "provider"
        assert len(appels) == 1, "second appel doit venir du cache, pas du reseau"

    async def test_refresh_force_le_rafraichissement(self, db_session, test_user):
        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)
        appels = [0]

        def handler(request: httpx.Request) -> httpx.Response:
            appels[0] += 1
            return httpx.Response(200, json={"data": [{"id": f"m{appels[0]}"}]})

        transport = httpx.MockTransport(handler)
        r1 = await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        r2 = await lister_modeles(
            db_session, test_user.id, provider.id, transport=transport, refresh=True
        )
        assert r1["models"] == ["m1"]
        assert r2["models"] == ["m2"]

    async def test_echec_n_est_pas_mis_en_cache(self, db_session, test_user):
        """Un provider qui refuse ne doit pas 'coller' au cache : un rappel
        immediat doit retenter (sinon un utilisateur qui vient de fixer sa cle
        verrait toujours l'ancien echec)."""
        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)
        etat = {"ok": False}

        def handler(request: httpx.Request) -> httpx.Response:
            if etat["ok"]:
                return httpx.Response(200, json={"data": [{"id": "vrai"}]})
            return httpx.Response(401, json={"error": {"message": "bad"}})

        transport = httpx.MockTransport(handler)
        r1 = await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        assert r1["source"] == "repli"

        etat["ok"] = True
        r2 = await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        assert r2["source"] == "provider"
        assert r2["models"] == ["vrai"]

    async def test_patch_invalide_le_cache(self, db_session, test_user):
        """Changer la cle ou le base_url d'un provider doit invalider le cache."""
        from app.schemas.agent_provider import AgentProviderUpdate

        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)
        appels = [0]

        def handler(request: httpx.Request) -> httpx.Response:
            appels[0] += 1
            return httpx.Response(200, json={"data": [{"id": f"m{appels[0]}"}]})

        transport = httpx.MockTransport(handler)
        await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        assert appels[0] == 1

        await svc.mettre_a_jour(
            db_session,
            test_user.id,
            provider.id,
            AgentProviderUpdate(api_key="sk-nouvelle-cle-abcdef"),
        )
        # Apres update, la cache doit avoir ete videe
        await lister_modeles(db_session, test_user.id, provider.id, transport=transport)
        assert appels[0] == 2, "PATCH doit invalider le cache /models"


class TestTesterRemonteLesModeles:
    """Le test de cle est le moment ou l'utilisateur signale une intention d'usage.

    C'est le bon moment pour populer la liste des modeles disponibles : le cache
    est chaud pour la premiere ouverture du dropdown, sans deuxieme aller-retour
    depuis le front.
    """

    async def test_succes_inclut_les_modeles_du_compte(self, db_session, test_user):
        svc._invalider_cache_modeles_tout()
        p = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/chat/completions"):
                return httpx.Response(200, json={})
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "gpt-y"}]})
            return httpx.Response(500)

        res = await service_tester(
            db_session, test_user.id, p.id, transport=httpx.MockTransport(handler)
        )
        assert res.ok is True
        assert res.models == ["gpt-x", "gpt-y"]

    async def test_echec_ne_lance_pas_l_appel_modeles(self, db_session, test_user):
        """Une cle invalide : inutile de lister les modeles, ne pas gaspiller."""
        svc._invalider_cache_modeles_tout()
        p = await _mk_provider(db_session, test_user.id)
        appels_models = [0]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/chat/completions"):
                return httpx.Response(401, json={"error": {"message": "bad key"}})
            if request.url.path.endswith("/models"):
                appels_models[0] += 1
                return httpx.Response(200, json={"data": []})
            return httpx.Response(500)

        res = await service_tester(
            db_session, test_user.id, p.id, transport=httpx.MockTransport(handler)
        )
        assert res.ok is False
        assert res.models is None
        assert appels_models[0] == 0

    @pytest.mark.asyncio
    async def test_latency_ms_present_sur_succes(self, db_session, test_user):
        """Un test reussi doit porter latency_ms > 0 (signal diagnostic pour
        identifier un provider lent)."""
        svc._invalider_cache_modeles_tout()
        p = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/chat/completions"):
                return httpx.Response(200, json={})
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "gpt-x"}]})
            return httpx.Response(500)

        res = await service_tester(
            db_session, test_user.id, p.id, transport=httpx.MockTransport(handler)
        )
        assert res.ok is True
        assert isinstance(res.latency_ms, int)
        assert res.latency_ms >= 0


@pytest.mark.asyncio
class TestListerModelesMetadonnees:
    async def test_openrouter_garde_context_et_prix(self, db_session, test_user):
        """OpenRouter renvoie context_length + pricing : les garder dans models."""
        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "openai/gpt-4o",
                            "context_length": 128000,
                            "pricing": {"prompt": "0.0025", "completion": "0.01"},
                        }
                    ]
                },
            )

        res = await lister_modeles(
            db_session, test_user.id, provider.id, transport=httpx.MockTransport(handler)
        )

        assert res["source"] == "provider"
        assert isinstance(res["models"], list)
        m = res["models"][0]
        assert isinstance(m, dict)
        assert m["id"] == "openai/gpt-4o"
        assert m["context_length"] == 128000
        assert m["pricing"] == {"prompt": "0.0025", "completion": "0.01"}

    async def test_ids_nus_restent_liste_str(self, db_session, test_user):
        """Sans context_length ni pricing, models reste list[str] (retro-compat)."""
        svc._invalider_cache_modeles_tout()
        provider = await _mk_provider(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

        res = await lister_modeles(
            db_session, test_user.id, provider.id, transport=httpx.MockTransport(handler)
        )

        assert res["source"] == "provider"
        assert res["models"] == ["m1", "m2"]
        assert all(isinstance(m, str) for m in res["models"])
