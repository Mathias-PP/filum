"""Un refus temporaire de debit ne doit pas passer pour un refus d'acces.

Mesure du 2026-08-16 depuis la VM de production : relire quinze sources
hebergees chez NCBI (PubMed, PMC) a la suite fait repondre 429 a la moitie
d'entre elles. Philum concluait « le site a refuse de nous laisser lire »,
alors que la meme URL rend son texte deux secondes plus tard. L'auteur·ice y
lisait un blocage editorial la ou il n'y avait qu'une file d'attente, et les
citations de ces sources restaient invérifiables.

Un 403 reste un refus stable, lui : on ne le retente pas.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.extractors.url_extractor import _html_scrape

_PAGE = "<html><head><title>Un article</title></head><body>Du texte lisible.</body></html>"


class _Reponse:
    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.headers = {"content-type": "text/html; charset=utf-8"}
        if retry_after is not None:
            self.headers["retry-after"] = retry_after
        self.text = _PAGE


class _Client:
    """Rejoue une suite de reponses prevue d'avance et compte les appels."""

    def __init__(self, journal: dict[str, Any], suite: list[_Reponse], **_kw: Any) -> None:
        self._journal = journal
        self._suite = suite
        journal["appels"] = 0

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, _url: str, **_kwargs: Any) -> _Reponse:
        i = self._journal["appels"]
        self._journal["appels"] += 1
        return self._suite[min(i, len(self._suite) - 1)]


@pytest.fixture
def sans_attente(monkeypatch):
    """Neutralise la pause pour que le test reste instantane, tout en la notant."""
    attentes: list[float] = []

    async def _dors(duree: float) -> None:
        attentes.append(duree)

    monkeypatch.setattr("app.extractors.url_extractor.asyncio.sleep", _dors)
    return attentes


def _branche(monkeypatch, journal: dict[str, Any], suite: list[_Reponse]) -> None:
    monkeypatch.setattr(
        "app.extractors.url_extractor.httpx.AsyncClient",
        lambda *a, **kw: _Client(journal, suite, **kw),
    )


@pytest.mark.asyncio
async def test_un_429_est_retente_et_la_page_finit_par_etre_lue(monkeypatch, sans_attente):
    journal: dict[str, Any] = {}
    _branche(monkeypatch, journal, [_Reponse(429), _Reponse(200)])

    meta = await _html_scrape("https://pubmed.ncbi.nlm.nih.gov/34176681/")

    assert journal["appels"] == 2
    assert meta is not None
    assert meta.access_blocked is False
    assert meta.title == "Un article"


@pytest.mark.asyncio
async def test_un_429_persistant_reste_un_refus(monkeypatch, sans_attente):
    journal: dict[str, Any] = {}
    _branche(monkeypatch, journal, [_Reponse(429)])

    meta = await _html_scrape("https://pubmed.ncbi.nlm.nih.gov/34176681/")

    assert meta is not None
    assert meta.access_blocked is True


@pytest.mark.asyncio
async def test_un_403_n_est_pas_retente(monkeypatch, sans_attente):
    #: Refus stable : reessayer ne ferait que doubler l'attente de l'auteur·ice.
    journal: dict[str, Any] = {}
    _branche(monkeypatch, journal, [_Reponse(403), _Reponse(200)])

    meta = await _html_scrape("https://onlinelibrary.wiley.com/doi/10.3322/caac.21834")

    assert journal["appels"] == 1
    assert meta is not None
    assert meta.access_blocked is True


@pytest.mark.asyncio
async def test_l_attente_demandee_par_le_site_est_respectee_sans_etre_subie(
    monkeypatch, sans_attente
):
    #: Un serveur peut demander une heure. On ne fait pas patienter une requete
    #: web autant : on tente une fois vite, et on renonce plutot que bloquer.
    journal: dict[str, Any] = {}
    _branche(monkeypatch, journal, [_Reponse(429, retry_after="3600"), _Reponse(200)])

    await _html_scrape("https://pubmed.ncbi.nlm.nih.gov/34176681/")

    assert sans_attente, "aucune pause observee"
    assert max(sans_attente) <= 5.0
