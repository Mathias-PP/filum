"""Plusieurs moteurs web configures : leurs resultats fusionnent, un moteur muet n'empeche rien."""

from __future__ import annotations

import pytest

from app.agent_tools import web


@pytest.fixture
def deux_moteurs(monkeypatch):
    monkeypatch.setattr(web.settings, "agent_web_search_provider", "tavily, brave")
    monkeypatch.setattr(web.settings, "agent_web_search_api_key", "cle-t, cle-b")


def test_les_moteurs_se_lisent_en_paires(deux_moteurs, monkeypatch):
    assert web.fournisseurs_web() == [("tavily", "cle-t"), ("brave", "cle-b")]
    monkeypatch.setattr(web.settings, "agent_web_search_api_key", "cle-t")
    assert web.fournisseurs_web() == [("tavily", "cle-t")]


@pytest.mark.asyncio
async def test_une_page_trouvee_par_deux_moteurs_passe_devant(deux_moteurs, monkeypatch):
    async def rechercher(provider, cle, query):
        if provider == "tavily":
            return [
                {"url": "https://a.example/seule", "title": "A", "snippet": "a"},
                {"url": "https://www.b.example/commune/", "title": "B", "snippet": ""},
            ]
        return [{"url": "https://b.example/commune", "title": "B", "snippet": "b"}]

    monkeypatch.setattr(web, "_rechercher", rechercher)
    resultats, repondu = await web.rechercher_web_fusionne("budget communal")

    assert repondu == ["tavily", "brave"]
    assert resultats[0]["title"] == "B"
    assert resultats[0]["moteurs"] == "tavily,brave"
    assert resultats[0]["snippet"] == "b"


@pytest.mark.asyncio
async def test_un_moteur_muet_n_empeche_pas_l_autre(deux_moteurs, monkeypatch):
    async def rechercher(provider, cle, query):
        if provider == "brave":
            raise RuntimeError("quota atteint")
        return [{"url": "https://a.example/x", "title": "X", "snippet": ""}]

    monkeypatch.setattr(web, "_rechercher", rechercher)
    rendu = await web._execute_web_search(None, {"query": "histoire du port"})
    assert rendu["moteurs"] == ["tavily"]
    assert [r["url"] for r in rendu["results"]] == ["https://a.example/x"]
