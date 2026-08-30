"""La cascade : NCBI, editeur, Europe PMC par DOI, le relais, puis l'archive.

Les replis sont ce qui separe « bloque par l'editeur » de « illisible ». Un
article CC-BY derriere un Cloudflare reste lisible, et le declarer illisible
accuse l'auteur·ice a la place du site.

Les trois premiers etages supposent quelque chose de la source : un hebergeur,
un DOI, un depot libre. Les deux derniers n'en supposent rien, et c'est pour
cela qu'ils existent : une enquete de presse bloquee ne releve d'aucun des
autres. Leur ordre entre eux n'est pas indifferent et les tests le fixent, le
relais rendant l'etat du jour la ou l'archive rend celui d'une capture passee.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints.excerpts import _texte_de_la_source
from app.extractors import (
    crossref_resume,
    europepmc_oracle,
    lecteur_relais,
    pmc_oracle,
    url_extractor,
    web_archive,
)


@pytest.fixture
def sans_reseau(monkeypatch):
    """Neutralise les six etages ; chaque test rebranche celui qu'il teste."""

    async def rien(*_a, **_k):
        return None

    async def sans_resume(*_a, **_k):
        return ""

    monkeypatch.setattr(pmc_oracle, "texte_ncbi", rien)
    monkeypatch.setattr(url_extractor, "_html_scrape", rien)
    monkeypatch.setattr(europepmc_oracle, "texte_europepmc", rien)
    monkeypatch.setattr(lecteur_relais, "texte_par_relais", rien)
    monkeypatch.setattr(web_archive, "texte_archive", rien)
    monkeypatch.setattr(crossref_resume, "texte_resume_crossref", sans_resume)


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
    monkeypatch.setattr(lecteur_relais, "texte_par_relais", jamais)
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


@pytest.mark.asyncio
async def test_le_relais_couvre_une_page_jamais_archivee(sans_reseau, monkeypatch):
    # Le cas qu'aucun etage precedent ne couvre : ni hebergeur connu, ni DOI,
    # ni depot libre, et aucune capture. C'est la moitie du web bloquant, dont
    # tout article publie du jour.
    vues: list[str] = []

    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def relais(url):
        vues.append(url)
        return "Le texte, dans son etat du jour."

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(lecteur_relais, "texte_par_relais", relais)

    assert await _texte_de_la_source("https://presse.example/enquete") == (
        "Le texte, dans son etat du jour.",
        False,
        True,
    )
    assert vues == ["https://presse.example/enquete"]


@pytest.mark.asyncio
async def test_le_relais_passe_avant_l_archive(sans_reseau, monkeypatch):
    # Les deux repondent, et l'ordre decide de ce que la fiche portera : l'etat
    # du jour, ou celui d'une capture parfois vieille de plusieurs annees. Un
    # extrait verifie contre une version perimee est une regression silencieuse,
    # d'ou ce test plutot qu'un commentaire.
    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def jamais(_url):
        raise AssertionError("l'archive ne doit pas etre sollicitee quand le relais repond")

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(lecteur_relais, "texte_par_relais", lambda _u: _du_jour())
    monkeypatch.setattr(web_archive, "texte_archive", jamais)

    texte, _bloque, _complet = await _texte_de_la_source("https://presse.example/enquete")
    assert texte == "Le texte, dans son etat du jour."


@pytest.mark.asyncio
async def test_l_archive_reste_le_filet_quand_le_relais_echoue(sans_reseau, monkeypatch):
    # Quota atteint ou relais en panne : sans ce dernier filet, brancher le
    # relais aurait retire de la couverture au lieu d'en ajouter.
    async def scrape(_url):
        return _Meta(page_text="", access_blocked=True)

    async def archive(_url):
        return "Le texte, tel que l'archive l'a capture."

    monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
    monkeypatch.setattr(web_archive, "texte_archive", archive)

    texte, _bloque, _complet = await _texte_de_la_source("https://presse.example/enquete")
    assert texte == "Le texte, tel que l'archive l'a capture."


class TestLeResumeCrossrefEnDernierRecours:
    """Ce que le serveur affiche par ailleurs doit pouvoir etre cite.

    Mesure du 2026-08-30 : l'agent lisait le resume Crossref d'un article par
    `get_url_metadata`, voulait en citer la premiere phrase, et se voyait
    repondre que la source n'avait pu etre obtenue par aucune voie. La preuve
    etait la, deposee par l'editeur, et le systeme la declarait inexistante.
    """

    @pytest.mark.asyncio
    async def test_il_sert_quand_aucun_etage_ne_rend_la_page(self, sans_reseau, monkeypatch):
        async def scrape(_url):
            return _Meta(page_text="", access_blocked=True, doi="10.1113/JP278810")

        async def resume(doi):
            assert doi == "10.1113/JP278810"
            return "Contrary to Warburg's original thesis, accelerated aerobic glycolysis..."

        monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
        monkeypatch.setattr(crossref_resume, "texte_resume_crossref", resume)

        texte, bloque, complet = await _texte_de_la_source("https://revue.example/article")
        assert texte.startswith("Contrary to Warburg's original thesis")
        # Le texte entier reste refuse : seul le resume a ete obtenu, et il ne
        # vient pas de la page. Annoncer la source lisible serait faux.
        assert (bloque, complet) == (True, False)

    @pytest.mark.asyncio
    async def test_il_ne_passe_jamais_devant_un_texte_entier(self, sans_reseau, monkeypatch):
        """Un resume ne remplace pas un article : il vient apres tous les autres."""

        async def scrape(_url):
            return _Meta(page_text="", access_blocked=True, doi="10.1113/JP278810")

        async def archive(_url):
            return "Le texte entier, tel que l'archive l'a capture."

        async def jamais(_doi):
            raise AssertionError("le resume ne doit pas etre demande quand la page a ete lue")

        monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
        monkeypatch.setattr(web_archive, "texte_archive", archive)
        monkeypatch.setattr(crossref_resume, "texte_resume_crossref", jamais)

        texte, _bloque, complet = await _texte_de_la_source("https://revue.example/article")
        assert texte == "Le texte entier, tel que l'archive l'a capture."
        assert complet is True

    @pytest.mark.asyncio
    async def test_sans_resume_depose_la_source_reste_illisible(self, sans_reseau, monkeypatch):
        """Elsevier n'en depose aucun : l'absence est ordinaire, pas un incident."""

        async def scrape(_url):
            return _Meta(page_text="", access_blocked=True, doi="10.1016/j.drup.2018.03.001")

        monkeypatch.setattr(url_extractor, "_html_scrape", scrape)
        assert await _texte_de_la_source("https://revue.example/article") == ("", True, True)


async def _corps() -> str:
    return "Le corps de l'article."


async def _du_jour() -> str:
    return "Le texte, dans son etat du jour."
