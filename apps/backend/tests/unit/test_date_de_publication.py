"""Une source se date par ce que sa page declare, sous toutes ses conventions courantes."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.extractors import lecture_page, url_extractor
from app.extractors.url_extractor import ExtractedMetadata, _date_de_publication


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><head>{html}</head><body></body></html>", "lxml")


def test_une_date_imbriquee_dans_le_json_ld_est_trouvee():
    json_ld = (
        '<script type="application/ld+json">{"@type": "Article", "mainEntityOfPage": '
        '{"@type": "WebPage", "datePublished": "2026-01-28"}}</script>'
    )
    assert _date_de_publication(_soup(json_ld)) == "2026-01-28"


@pytest.mark.parametrize(
    ("balise", "attendue"),
    [
        ('<meta name="ms.date" content="2026-07-29T00:00:00Z">', "2026-07-29"),
        ('<meta name="published_date" content="2026-01-28">', "2026-01-28"),
        ('<meta name="DC.date.issued" content="2014">', "2014-01-01"),
        ('<meta itemprop="datePublished" content="2020-03-15">', "2020-03-15"),
    ],
)
def test_les_conventions_d_editeurs_sont_lues(balise, attendue):
    assert _date_de_publication(_soup(balise)) == attendue


def test_la_parution_passe_avant_la_mise_a_jour_qui_sert_a_defaut():
    deux = (
        '<meta property="article:modified_time" content="2026-08-01">'
        '<meta name="citation_publication_date" content="2017/06/12">'
    )
    assert _date_de_publication(_soup(deux)) == "2017-06-12"
    seule = '<meta property="og:article:modified_time" content="2026-04-02">'
    assert _date_de_publication(_soup(seule)) == "2026-04-02"


def test_la_revision_en_ligne_ne_date_pas_l_oeuvre():
    assert _date_de_publication(_soup('<meta name="citation_online_date" content="2023">')) is None


@pytest.mark.asyncio
async def test_une_page_lue_par_le_relais_garde_sa_date(monkeypatch):
    async def refus(url):
        return ExtractedMetadata(access_blocked=True)

    async def relais(url):
        return (
            "Agent Harness",
            "Title: Agent Harness\nPublished Time: 2026-01-28T10:00:00Z\n\nAn agent harness is...",
        )

    async def aucune_archive(url):
        return None

    monkeypatch.setattr(url_extractor, "_html_scrape", refus)
    monkeypatch.setattr(lecture_page, "page_par_relais", relais)
    monkeypatch.setattr(lecture_page, "html_archive", aucune_archive)
    meta = await lecture_page.metadonnees_de_la_page("https://exemple.test/a", avec_modele=False)
    assert meta is not None and meta.published_at == "2026-01-28"
