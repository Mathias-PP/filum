"""Une requete sans langue annoncee ne lit pas Springer Nature.

Mesure du 2026-08-16 sur `10.1186/s12943-025-02369-9`, depuis la VM de
production : sans `Accept-Language`, le serveur renvoie 200 et 3 036 octets
d'interstitiel ; avec, 992 744 octets d'article. Philum classait le premier en
« page bloquee », et toute source hebergee chez Springer ou Nature se retrouvait
sans texte : ni suggestion de citation, ni relecture, ni scraping HTML.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.extractors.url_extractor import _html_scrape


class _Reponse:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    text = "<html><head><title>Un article</title></head><body>Du texte lisible.</body></html>"


class _Client:
    """Enregistre les en-tetes passes au constructeur d'httpx.AsyncClient."""

    def __init__(self, journal: dict[str, Any], **kwargs: Any) -> None:
        journal["headers"] = kwargs.get("headers")

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, _url: str, **_kwargs: Any) -> _Reponse:
        return _Reponse()


@pytest.mark.asyncio
async def test_le_scraping_annonce_une_langue_et_un_type_accepte(monkeypatch):
    journal: dict[str, Any] = {}
    monkeypatch.setattr(
        "app.extractors.url_extractor.httpx.AsyncClient",
        lambda *a, **kw: _Client(journal, **kw),
    )

    await _html_scrape("https://link.springer.com/article/10.1186/s12943-025-02369-9")

    envoyes = journal["headers"]
    assert "Accept-Language" in envoyes
    assert "text/html" in envoyes["Accept"]
    #: L'identification reste, elle : Crossref et les editeurs la demandent.
    assert "Philum" in envoyes["User-Agent"]
