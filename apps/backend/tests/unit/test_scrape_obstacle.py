"""Un obstacle de lecture doit se dire, jamais se taire ni s'imputer a l'auteur·ice.

Mesure du 2026-08-16 depuis la VM de production, en relisant les sources d'une
fiche scientifique reelle :

- PubMed repond desormais **HTTP 203** avec un defi anti-robot (« Cookies must
  be enabled », en-tete `X-NCBI-CAPTCHA`). Philum sortait sur `status != 200`
  avant meme son detecteur d'obstacle : ni « lu », ni « refuse », rien.
- Un DOI Elsevier atterrit sur `linkinghub` qui rend une page de 11 caracteres
  intitulee « Redirecting ». Philum la comptait pour une page lue. A la
  relecture, chaque extrait y devenait `missing`, c'est-a-dire *absent de la
  source* : la citation etait accusee a la place du site.

Les deux corrections disent la meme chose : on ne declare avoir lu que ce qu'on
a lu.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.extractors.url_extractor import _html_scrape

_DEFI_NCBI = """<html><head><title>pubmed.ncbi.nlm.nih.gov</title></head><body>
<div id="cookie-required"><h1>Cookies must be enabled</h1>
<p>Enable cookies for pubmed.ncbi.nlm.nih.gov and reload this page to continue.</p></div>
</body></html>"""

_REDIRECTION_ELSEVIER = """<html><head><title>Redirecting</title></head>
<body>Redirecting</body></html>"""

_ARTICLE = (
    "<html><head><title>Un article</title></head><body>"
    + "Du texte lisible et long. " * 200
    + "</body></html>"
)


class _Reponse:
    def __init__(self, status_code: int, corps: str) -> None:
        self.status_code = status_code
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.text = corps


class _Client:
    def __init__(self, reponse: _Reponse, **_kw: Any) -> None:
        self._reponse = reponse

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, _url: str, **_kwargs: Any) -> _Reponse:
        return self._reponse


def _branche(monkeypatch, reponse: _Reponse) -> None:
    monkeypatch.setattr(
        "app.extractors.url_extractor.httpx.AsyncClient",
        lambda *a, **kw: _Client(reponse, **kw),
    )


@pytest.mark.asyncio
async def test_un_defi_servi_en_203_est_un_refus_et_non_un_silence(monkeypatch):
    _branche(monkeypatch, _Reponse(203, _DEFI_NCBI))

    meta = await _html_scrape("https://pubmed.ncbi.nlm.nih.gov/34176681/")

    assert meta is not None, "un refus muet ne laisse rien a dire a l'auteur·ice"
    assert meta.access_blocked is True


@pytest.mark.asyncio
async def test_une_page_de_redirection_ne_passe_pas_pour_une_page_lue(monkeypatch):
    #: Sinon la relecture declare l'extrait « absent de la source » alors que la
    #: source n'a jamais ete ouverte.
    _branche(monkeypatch, _Reponse(200, _REDIRECTION_ELSEVIER))

    meta = await _html_scrape("https://doi.org/10.1016/j.annonc.2021.05.806")

    assert meta is not None
    assert meta.access_blocked is True


@pytest.mark.asyncio
async def test_un_article_servi_en_203_reste_lu(monkeypatch):
    #: Tout 2xx n'est pas un obstacle : c'est le contenu qui tranche.
    _branche(monkeypatch, _Reponse(203, _ARTICLE))

    meta = await _html_scrape("https://exemple.org/article")

    assert meta is not None
    assert meta.access_blocked is False
    assert meta.title == "Un article"
    assert meta.page_text and len(meta.page_text) > 2000


@pytest.mark.asyncio
async def test_un_article_qui_parle_de_redirection_reste_lu(monkeypatch):
    corps = (
        "<html><head><title>Redirections HTTP</title></head><body>"
        + "Redirecting est le titre que sert linkinghub. " * 100
        + "</body></html>"
    )
    _branche(monkeypatch, _Reponse(200, corps))

    meta = await _html_scrape("https://exemple.org/redirections")

    assert meta is not None
    assert meta.access_blocked is False
