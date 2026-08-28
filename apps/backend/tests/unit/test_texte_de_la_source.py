"""La cascade de lecture d'une source : NCBI, editeur, puis Europe PMC.

Le repli par DOI est ce qui separe « bloque par l'editeur » de « illisible ».
Un article CC-BY derriere un Cloudflare reste lisible, et le declarer illisible
accuse l'auteur·ice a la place du site.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints.excerpts import _texte_de_la_source
from app.extractors import europepmc_oracle, pmc_oracle, url_extractor


@pytest.fixture
def sans_reseau(monkeypatch):
    """Neutralise les trois etages ; chaque test rebranche celui qu'il teste."""

    async def rien(*_a, **_k):
        return None

    monkeypatch.setattr(pmc_oracle, "texte_ncbi", rien)
    monkeypatch.setattr(url_extractor, "_html_scrape", rien)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", rien)


class _Meta:
    def __init__(self, page_text=None, access_blocked=False, doi=None):
        self.page_text = page_text
        self.access_blocked = access_blocked
        self.doi = doi


@pytest.mark.asyncio
async def test_sans_url_rien_a_lire(sans_reseau):
    assert await _texte_de_la_source(None) == ("", False, True)


@pytest.mark.asyncio
async def test_l_editeur_qui_repond_court_la_cascade(sans_reseau, monkeypatch):
    async def scrape(_url):
        return _Meta(page_text="Le texte de l'article.")

    async def jamais(_doi):
        raise AssertionError("Europe PMC ne doit pas etre appele quand l'editeur repond")

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", jamais)
    assert await _texte_de_la_source("https://example.org/a") == (
        "Le texte de l'article.",
        False,
        True,
    )


@pytest.mark.asyncio
async def test_un_editeur_bloquant_passe_par_le_doi_de_l_url(sans_reseau, monkeypatch):
    vus: list[str] = []

    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def europepmc(doi):
        vus.append(doi)
        return "Le texte integral, servi par le depot libre."

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", europepmc)

    texte, bloque, complet = await _texte_de_la_source(
        "https://doi.org/10.1186/s10020-025-01205-6"
    )
    assert vus == ["10.1186/s10020-025-01205-6"]
    # Le texte a ete obtenu : la source n'est plus « refusee », sinon
    # l'interface afficherait un blocage sur un article qu'on vient de lire.
    assert (texte, bloque, complet) == (
        "Le texte integral, servi par le depot libre.",
        False,
        True,
    )


@pytest.mark.asyncio
async def test_le_doi_declare_par_la_page_sert_de_repli(sans_reseau, monkeypatch):
    vus: list[str] = []

    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True, doi="10.1000/xyz")

    async def europepmc(doi):
        vus.append(doi)
        return None

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", europepmc)

    assert await _texte_de_la_source("https://revue.example/article") == ("", True, True)
    assert vus == ["10.1000/xyz"]


@pytest.mark.asyncio
async def test_le_blocage_survit_a_l_echec_du_repli(sans_reseau, monkeypatch):
    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    assert await _texte_de_la_source("https://example.org/a") == ("", True, True)
