"""La cascade : NCBI, editeur, Europe PMC par DOI, puis l'archive du web.

Les replis sont ce qui separe « bloque par l'editeur » de « illisible ». Un
article CC-BY derriere un Cloudflare reste lisible, et le declarer illisible
accuse l'auteur·ice a la place du site.

Les trois premiers etages supposent quelque chose de la source : un hebergeur,
un DOI, un depot libre. Le dernier n'en suppose rien, et c'est pour cela qu'il
existe : une enquete de presse bloquee ne releve d'aucun des autres.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints.excerpts import _texte_de_la_source
from app.extractors import europepmc_oracle, pmc_oracle, url_extractor, web_archive


@pytest.fixture
def sans_reseau(monkeypatch):
    """Neutralise les quatre etages ; chaque test rebranche celui qu'il teste."""

    async def rien(*_a, **_k):
        return None

    monkeypatch.setattr(pmc_oracle, "texte_ncbi", rien)
    monkeypatch.setattr(url_extractor, "_html_scrape", rien)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", rien)
    monkeypatch.setattr(web_archive, "texte_archive", rien)


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

    async def jamais(_arg):
        raise AssertionError("aucun repli ne doit etre appele quand l'editeur repond")

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", jamais)
    monkeypatch.setattr(web_archive, "texte_archive", jamais)
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

    texte, bloque, complet = await _texte_de_la_source("https://doi.org/10.1186/s10020-025-01205-6")
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


@pytest.mark.asyncio
async def test_une_source_sans_doi_passe_par_l_archive(sans_reseau, monkeypatch):
    # Le cas que les trois premiers etages ne couvrent pas : ni hebergeur
    # connu, ni DOI, ni depot libre. Sans ce dernier etage, une enquete de
    # presse bloquee est declaree illisible alors qu'elle est archivee.
    vues: list[str] = []

    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def archive(url):
        vues.append(url)
        return "Le texte, tel que l'archive l'a capture."

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(web_archive, "texte_archive", archive)

    assert await _texte_de_la_source("https://presse.example/enquete") == (
        "Le texte, tel que l'archive l'a capture.",
        False,
        True,
    )
    assert vues == ["https://presse.example/enquete"]


@pytest.mark.asyncio
async def test_le_depot_libre_passe_avant_l_archive(sans_reseau, monkeypatch):
    # Europe PMC rend le corps de l'article ; l'archive rend la page entiere,
    # menus compris, dans l'etat d'un jour passe. A texte egal, le premier est
    # meilleur : inverser l'ordre degraderait chaque lecture scientifique.
    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def jamais(_url):
        raise AssertionError("l'archive ne doit pas etre sollicitee apres un succes")

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", lambda _d: _corps())
    monkeypatch.setattr(web_archive, "texte_archive", jamais)

    texte, _bloque, _complet = await _texte_de_la_source("https://doi.org/10.1000/xyz")
    assert texte == "Le corps de l'article."


async def _corps() -> str:
    return "Le corps de l'article."
