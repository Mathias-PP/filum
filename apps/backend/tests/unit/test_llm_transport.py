"""Ce qui sépare un LLM inerte d'un LLM vivant.

Les sept appels du backend nomment des alias de tâche — `biblio-parse`,
`excerpt-suggest`, `metadata-extract` — qui ne désignent aucun modèle
existant : seul un proxy LiteLLM sait les traduire. Sans proxy, l'appel part
vers un modèle inconnu et la fonctionnalité meurt en silence, ce qui est
exactement l'état de la production (ADR-035). D'où la première règle tenue
ici : un alias non résolu ne doit jamais partir tel quel quand on a dit vers
quel modèle réel aller.

La seconde règle vient d'une asymétrie entre providers. On demande une sortie
contrainte par schéma parce que c'est la seule forme qui garantisse du JSON ;
mais les schémas que produit Pydantic portent des `anyOf` et des `$defs` que
certains providers refusent au niveau de la requête. Un refus de la *forme*
n'est pas un refus de la *tâche* : abandonner là rendrait la couche LLM
dépendante du provider, ce qu'elle n'a aucune raison d'être.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.services import llm


class _Reponse:
    def __init__(self, status: int, payload: dict | None = None, text: str = ""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def _contenu(brut: str) -> dict:
    return {"choices": [{"message": {"content": brut}}]}


class _FauxClient:
    """Enregistre chaque requête et sert les réponses dans l'ordre."""

    envois: list[dict] = []
    reponses: list[_Reponse] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        _FauxClient.envois.append({"url": url, "json": json, "headers": headers})
        return _FauxClient.reponses.pop(0)


@pytest.fixture
def transport(monkeypatch):
    _FauxClient.envois = []
    _FauxClient.reponses = []
    monkeypatch.setattr(llm.httpx, "AsyncClient", _FauxClient)
    settings = get_settings()
    monkeypatch.setattr(settings, "litellm_base_url", "https://exemple.test/v1beta/openai")
    monkeypatch.setattr(settings, "litellm_master_key", "cle-de-test")
    monkeypatch.setattr(settings, "llm_direct_model", "")
    return _FauxClient


class TestRacineConfiguree:
    """Deux façons d'annoncer une racine, une seule adresse juste par cas.

    L'erreur est muette des deux côtés : un `/v1` en trop rend un 404 que la
    couche avale (elle ne lève jamais), un `/v1` manquant aussi. Rien dans
    l'interface ne distinguerait « le modèle n'a rien trouvé » de « l'appel
    n'est jamais arrivé ».
    """

    def test_un_hote_nu_recoit_le_prefixe_du_proxy(self):
        assert llm.url_chat("http://litellm:4000") == "http://litellm:4000/v1/chat/completions"

    def test_une_racine_qui_porte_deja_son_chemin_nest_pas_redoublee(self):
        # Gemini expose sa surface OpenAI sous `/v1beta/openai`.
        assert (
            llm.url_chat("https://generativelanguage.googleapis.com/v1beta/openai")
            == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        )

    def test_une_barre_finale_ne_change_rien(self):
        assert llm.url_chat("http://litellm:4000/") == "http://litellm:4000/v1/chat/completions"


class TestResolutionAlias:
    def test_sans_modele_direct_l_alias_part_tel_quel(self, transport, monkeypatch):
        # Mode proxy : c'est LiteLLM qui traduit, le backend n'a rien à décider.
        monkeypatch.setattr(get_settings(), "llm_direct_model", "")
        assert llm.resoudre_modele("biblio-parse") == "biblio-parse"

    def test_le_modele_direct_court_circuite_l_alias(self, transport, monkeypatch):
        # Sans proxy, personne ne traduit : laisser passer l'alias serait un 404.
        monkeypatch.setattr(get_settings(), "llm_direct_model", "gemini-3.6-flash")
        assert llm.resoudre_modele("biblio-parse") == "gemini-3.6-flash"
        assert llm.resoudre_modele("metadata-extract") == "gemini-3.6-flash"

    @pytest.mark.asyncio
    async def test_c_est_le_modele_resolu_qui_est_envoye(self, transport, monkeypatch):
        monkeypatch.setattr(get_settings(), "llm_direct_model", "gemini-3.6-flash")
        transport.reponses = [_Reponse(200, _contenu('{"excerpts": []}'))]
        await llm.suggest_excerpts("Un texte.")
        assert transport.envois[0]["json"]["model"] == "gemini-3.6-flash"


class TestRepliSurSchemaRefuse:
    @pytest.mark.asyncio
    async def test_un_schema_refuse_ne_tue_pas_la_tache(self, transport):
        # 400 = le provider refuse la *forme* de la demande. La tâche, elle,
        # reste faisable en demandant du JSON libre et en validant en aval.
        transport.reponses = [
            _Reponse(400, text="Invalid JSON schema: anyOf not supported"),
            _Reponse(200, _contenu('{"excerpts": ["Un passage."]}')),
        ]
        assert await llm.suggest_excerpts("Un texte.") == ["Un passage."]

    @pytest.mark.asyncio
    async def test_le_repli_recopie_le_schema_dans_la_consigne(self, transport):
        transport.reponses = [
            _Reponse(400, text="unsupported"),
            _Reponse(200, _contenu('{"excerpts": []}')),
        ]
        await llm.suggest_excerpts("Un texte.")
        second = transport.envois[1]["json"]
        assert second["response_format"] == {"type": "json_object"}
        # Sans le schéma sous les yeux, le modèle n'a aucun moyen de deviner
        # la forme attendue : le repli serait une perte de garantie sèche.
        assert "excerpts" in second["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_une_panne_reelle_reste_une_panne(self, transport):
        # 500 n'est pas un désaccord sur la forme : ne pas insister.
        transport.reponses = [_Reponse(500, text="boom")]
        assert await llm.suggest_excerpts("Un texte.") is None
        assert len(transport.envois) == 1


class TestFormeDeLaRequete:
    @pytest.mark.asyncio
    async def test_la_cle_part_en_bearer_sur_le_chemin_openai(self, transport):
        transport.reponses = [_Reponse(200, _contenu('{"excerpts": []}'))]
        await llm.suggest_excerpts("Un texte.")
        envoi = transport.envois[0]
        assert envoi["url"] == "https://exemple.test/v1beta/openai/chat/completions"
        assert envoi["headers"]["Authorization"] == "Bearer cle-de-test"
        assert envoi["json"]["temperature"] == 0

    @pytest.mark.asyncio
    async def test_une_reponse_illisible_ne_remonte_pas_en_exception(self, transport):
        # Le contrat de toute la couche : ne jamais lever. L'appelant garde son
        # résultat déterministe plutôt que de voir la requête entière échouer.
        transport.reponses = [_Reponse(200, _contenu("ceci n'est pas du JSON"))]
        assert await llm.suggest_excerpts("Un texte.") is None

    @pytest.mark.asyncio
    async def test_sans_url_configuree_rien_ne_part_sur_le_reseau(self, transport, monkeypatch):
        monkeypatch.setattr(get_settings(), "litellm_base_url", "")
        assert await llm.suggest_excerpts("Un texte.") is None
        assert transport.envois == []


class TestIntitulesDeMorceaux:
    @pytest.mark.asyncio
    async def test_les_intitules_suivent_le_repli_comme_le_reste(self, transport):
        transport.reponses = [
            _Reponse(400, text="unsupported"),
            _Reponse(200, _contenu(json.dumps({"titles": ["Mémoire de travail", ""]}))),
        ]
        titres = await llm.suggest_chunk_titles(["Un passage.", "Un autre."])
        # La chaîne vide reste None : un intitulé faux se recopierait dans la
        # fiche sans que rien ne signale qu'il ne désigne pas le bon passage.
        assert titres == ["Mémoire de travail", None]
