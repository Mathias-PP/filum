"""Les liens cites dans le corps d'une page menent aux sources de la source."""

from __future__ import annotations

import httpx
import pytest

from app.core import url_safety
from app.extractors import body_links

HTML = """
<html><body>
<nav><a href="https://site.test/accueil">Accueil</a></nav>
<main><p>Selon <a href="https://rapport.test/etude">le rapport de l'agence</a>, les émissions
du transport ont baissé de onze pour cent après l'introduction de la taxe, un chiffre
repris depuis par plusieurs équipes.</p></main>
</body></html>
"""


def _page(monkeypatch, reponse: httpx.Response) -> None:
    vrai = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(lambda requete: reponse)
        kwargs.pop("event_hooks", None)
        return vrai(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(url_safety, "assert_url_is_safe", lambda url, **_: None)


@pytest.mark.asyncio
async def test_les_liens_du_texte_sont_rendus_sans_la_navigation(monkeypatch):
    _page(monkeypatch, httpx.Response(200, text=HTML, headers={"content-type": "text/html"}))
    liens = await body_links.liens_de_la_page("https://site.test/billet")
    assert [lien.url for lien in liens] == ["https://rapport.test/etude"]
    assert liens[0].raw_text == "le rapport de l'agence"


@pytest.mark.asyncio
async def test_une_reponse_qui_n_est_pas_une_page_ne_rend_aucun_lien(monkeypatch):
    _page(monkeypatch, httpx.Response(200, json={"a": 1}))
    assert await body_links.liens_de_la_page("https://site.test/api") == []


@pytest.mark.asyncio
async def test_une_adresse_interdite_n_est_pas_lue(monkeypatch):
    def interdite(url, **_):
        raise url_safety.UnsafeUrlError("reseau prive")

    monkeypatch.setattr(url_safety, "assert_url_is_safe", interdite)
    assert await body_links.liens_de_la_page("http://10.0.0.1/") == []
