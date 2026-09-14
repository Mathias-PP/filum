"""Les corpus academiques rendent des candidates reelles, sans jamais faire echouer l'agent.

Formes de reponse relevees le 2026-09-14 sur les API reelles.
"""

from __future__ import annotations

import httpx
import pytest

from app.extractors import recherche_litterature
from app.extractors.recherche_litterature import (
    candidate_europepmc,
    candidate_openalex,
    chercher_europepmc,
    chercher_openalex,
    voisinage_openalex,
)

TRAVAIL = {
    "id": "https://openalex.org/W1482806521",
    "doi": "https://doi.org/10.1000/retrograde",
    "display_name": "Retrograde menstruation in healthy women and in patients with endometriosis.",
    "publication_year": 1984,
    "cited_by_count": 1016,
    "type": "article",
    "open_access": {"is_oa": False, "oa_url": None},
    "primary_location": {
        "landing_page_url": "https://pubmed.ncbi.nlm.nih.gov/6234483",
        "source": {"display_name": "Obstetrics and gynecology"},
    },
    "authorships": [{"author": {"display_name": "J. Halme"}}],
}

ARTICLE_PMC = {
    "pmid": "42116741",
    "pmcid": "PMC9999999",
    "doi": "10.1093/reprod/xaag056",
    "title": "Peritoneal hypoxia as a gatekeeper between retrograde menstruation and endometriosis",
    "authorString": "Gabbay U, Schonman R.",
    "pubYear": "2026",
    "isOpenAccess": "Y",
    "citedByCount": "3",
    "journalTitle": "Reproduction",
    "pubTypeList": {"pubType": ["Review", "Journal Article"]},
}


def _transport(monkeypatch, gestionnaire):
    vrai = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(gestionnaire)
        return vrai(*args, **kwargs)

    monkeypatch.setattr(recherche_litterature.httpx, "AsyncClient", client)


def test_un_passage_semantic_scholar_porte_son_texte_et_sa_section():
    c = recherche_litterature.candidate_passage_s2(
        {
            "snippet": {
                "text": "Retrograde menstruation occurs in most women.",
                "section": "Results",
            },
            "score": 0.56,
            "paper": {
                "corpusId": "1234",
                "title": "Menstruation",
                "authors": [{"name": "A. Auteur"}],
            },
        }
    )
    assert c is not None
    assert c.url == "https://api.semanticscholar.org/CorpusId:1234"
    assert c.passage == "Retrograde menstruation occurs in most women."
    assert c.raisons == ["passage de la section « Results »"]
    assert recherche_litterature.candidate_passage_s2({"snippet": {}, "paper": {}}) is None


@pytest.mark.asyncio
async def test_sans_cle_semantic_scholar_aucun_appel(monkeypatch):
    from app.core.config import get_settings

    def gestionnaire(requete):  # pragma: no cover
        raise AssertionError("aucun appel sans cle")

    monkeypatch.setattr(get_settings(), "semantic_scholar_api_key", "")
    _transport(monkeypatch, gestionnaire)
    assert await recherche_litterature.chercher_passages_s2("endometriosis") == []


def test_un_travail_openalex_devient_une_candidate_par_son_doi():
    c = candidate_openalex(TRAVAIL)
    assert c is not None
    assert c.url == "https://doi.org/10.1000/retrograde"
    assert (c.famille, c.annee, c.citations, c.revue) == (
        "litterature",
        1984,
        1016,
        "Obstetrics and gynecology",
    )
    assert c.auteurs == "J. Halme"


def test_sans_doi_l_adresse_de_la_page_sert():
    c = candidate_openalex({**TRAVAIL, "doi": None})
    assert c is not None and c.url == "https://pubmed.ncbi.nlm.nih.gov/6234483"
    assert candidate_openalex({**TRAVAIL, "display_name": ""}) is None


def test_un_article_europepmc_libre_porte_son_acces_libre():
    c = candidate_europepmc(ARTICLE_PMC)
    assert c is not None
    assert c.url == "https://doi.org/10.1093/reprod/xaag056"
    assert c.acces_libre_url == "https://europepmc.org/article/PMC/9999999"
    assert (c.annee, c.citations, c.famille) == (2026, 3, "biomedical")
    assert "Review" in (c.type or "")


@pytest.mark.asyncio
async def test_la_recherche_openalex_passe_la_requete_en_plein_texte(monkeypatch):
    vues: list[httpx.URL] = []

    def gestionnaire(requete):
        vues.append(requete.url)
        return httpx.Response(200, json={"results": [TRAVAIL]})

    _transport(monkeypatch, gestionnaire)
    candidates = await chercher_openalex("retrograde menstruation", limite=3)
    assert len(candidates) == 1
    assert vues[0].params["search"] == "retrograde menstruation"
    assert vues[0].params["per_page"] == "3"


@pytest.mark.asyncio
async def test_un_corpus_en_panne_rend_une_liste_vide(monkeypatch):
    def gestionnaire(requete):
        raise httpx.ConnectError("injoignable")

    _transport(monkeypatch, gestionnaire)
    assert await chercher_europepmc("droit de greve") == []
    assert await chercher_openalex("droit de greve") == []


@pytest.mark.asyncio
async def test_les_citants_d_un_article_pivot_sont_les_plus_recents(monkeypatch):
    vues: list[httpx.URL] = []

    def gestionnaire(requete):
        vues.append(requete.url)
        if "/works/doi:" in str(requete.url):
            return httpx.Response(
                200, json={"id": "https://openalex.org/W42", "referenced_works": []}
            )
        return httpx.Response(200, json={"results": [TRAVAIL]})

    _transport(monkeypatch, gestionnaire)
    candidates = await voisinage_openalex("10.1000/pivot", sens="citants", limite=5)

    assert candidates and candidates[0].raisons == ["cite l'article pivot"]
    liste = vues[-1]
    assert liste.params["filter"] == "cites:W42"
    assert liste.params["sort"] == "publication_date:desc"


@pytest.mark.asyncio
async def test_toutes_les_references_sont_demandees_par_paquets_de_cent(monkeypatch):
    references = [f"https://openalex.org/W{n}" for n in range(150)]
    filtres: list[str] = []

    def gestionnaire(requete):
        if "/works/doi:" in str(requete.url):
            return httpx.Response(
                200, json={"id": "https://openalex.org/W42", "referenced_works": references}
            )
        filtre = requete.url.params["filter"]
        filtres.append(filtre)
        rang = len(filtres)
        travail = {
            **TRAVAIL,
            "doi": f"https://doi.org/10.1000/ref{rang}",
            "cited_by_count": 10 * rang,
        }
        return httpx.Response(200, json={"results": [travail]})

    _transport(monkeypatch, gestionnaire)
    candidates = await voisinage_openalex("10.1000/pivot", sens="references")

    assert [f.count("|") + 1 for f in filtres] == [100, 50]
    assert [c.doi for c in candidates] == ["10.1000/ref2", "10.1000/ref1"]


@pytest.mark.asyncio
async def test_les_references_d_un_article_sans_references_ne_font_pas_d_appel_de_liste(
    monkeypatch,
):
    vues: list[httpx.URL] = []

    def gestionnaire(requete):
        vues.append(requete.url)
        return httpx.Response(200, json={"id": "https://openalex.org/W42", "referenced_works": []})

    _transport(monkeypatch, gestionnaire)
    assert await voisinage_openalex("10.1000/pivot", sens="references") == []
    assert len(vues) == 1


@pytest.mark.asyncio
async def test_les_citants_se_cherchent_par_pertinence_avec_la_question(monkeypatch):
    vues: list[httpx.URL] = []

    def gestionnaire(requete):
        vues.append(requete.url)
        if "/works/doi:" in str(requete.url):
            return httpx.Response(
                200, json={"id": "https://openalex.org/W42", "referenced_works": []}
            )
        return httpx.Response(200, json={"results": [TRAVAIL]})

    _transport(monkeypatch, gestionnaire)
    await voisinage_openalex("10.1000/pivot", sens="citants", requete="effet sur le transport")
    assert vues[-1].params["search"] == "effet sur le transport"
    assert vues[-1].params["sort"] == "relevance_score:desc"
    assert vues[-1].params["filter"] == "cites:W42"
