"""Archiver la ressource, pas le panneau qui y mene.

Mesure en prod le 2026-08-04, apres #262, #265, #266 et #267 : la fiche de
152 sources restait a **zero archivee**, et les 148 URL en attente etaient
toutes des `https://doi.org/...`.

`doi.org` est un resolveur. Toutes ses captures dans l'archive sont des
`302` -- verifie par `curl` : la requete CDX sans filtre renvoie trois
captures, toutes `302`, et avec `filter=statuscode:200` elle renvoie `[]`.
Le sondage ne pouvait donc rien trouver, et Save Page Now n'aurait capture
qu'une redirection, qui ne preserve aucun contenu.

Une fois l'URL resolue, la meme requete trouve bien une capture `200` :

- `doi.org/10.1002/brb3.244` -> `onlinelibrary.wiley.com/doi/10.1002/brb3.244`
  -> capture `200` du 2024-01-09
- `doi.org/10.1146/annurev.neuro.24.1.167` -> `annualreviews.org/doi/...`
  -> captures `200` de 2018 et 2019

La detection se fait par **comportement** -- cette URL redirige-t-elle ? --
et jamais par liste de domaines : un raccourcisseur, un « linking hub »
d'editeur ou le prochain resolveur en date passeraient sinon au travers.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.services import wayback as wb


class _FakeDb:
    pass


class _Recorder(wb.WaybackService):
    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.triggered: list[str] = []
        self.polled: list[str] = []
        self.written: list[tuple] = []
        self.redirects: dict[str, str] = {}
        self.snapshots: dict[str, str] = {}

    async def _resolve(self, url: str) -> str:
        return self.redirects.get(url, url)

    async def _trigger_save(self, url: str) -> None:
        self.triggered.append(url)

    async def _lookup_snapshot(self, url: str) -> tuple[str, str | None] | None:
        self.polled.append(url)
        snap = self.snapshots.get(url)
        return (snap, "20240109171411") if snap else None

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


@pytest.fixture
def no_sleep(monkeypatch):
    async def _sleep(d: float) -> None:
        return None

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)


class TestLeLotViseLaRessource:
    def test_le_sondage_porte_sur_la_cible_pas_sur_le_resolveur(self, no_sleep):
        svc = _Recorder()
        svc.redirects["https://doi.org/10.1002/brb3.244"] = (
            "https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"
        )

        asyncio.run(svc.archive_batch([(uuid4(), "https://doi.org/10.1002/brb3.244")]))

        assert svc.polled == ["https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"]

    def test_la_capture_est_demandee_sur_la_cible(self, no_sleep):
        """Capturer une redirection ne preserve rien."""
        svc = _Recorder()
        svc.redirects["https://doi.org/10.1002/brb3.244"] = (
            "https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"
        )

        asyncio.run(svc.archive_batch([(uuid4(), "https://doi.org/10.1002/brb3.244")]))

        assert svc.triggered == ["https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"]

    def test_une_url_qui_ne_redirige_pas_est_sondee_telle_quelle(self, no_sleep):
        svc = _Recorder()

        asyncio.run(svc.archive_batch([(uuid4(), "https://example.org/article")]))

        assert svc.polled == ["https://example.org/article"]


class TestLaResolutionNeConclutJamais:
    """Ne pas savoir resoudre est une ignorance, pas une reponse."""

    def _svc(self) -> wb.WaybackService:
        return wb.WaybackService(_FakeDb(), None)  # type: ignore[arg-type]

    def _pages(self, monkeypatch, pages: dict[str, tuple[str, bytes]]):
        """Un web factice : url demandee -> (url finale HTTP, corps HTML).

        Les redirections HTTP sont deja resolues par le client reel ; ce faux
        ne simule donc que leur resultat, plus le corps ou peut se cacher une
        redirection d'un autre genre.
        """

        class _Stream:
            def __init__(self, final: str, body: bytes) -> None:
                self.url = final
                self.headers = {"content-type": "text/html; charset=utf-8"}
                self._body = body

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def aiter_bytes(self):
                yield self._body

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def stream(self, method, url, **k):
                if url not in pages:
                    raise httpx.ConnectError(f"no route to {url}")
                return _Stream(*pages[url])

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

    def test_la_cible_finale_est_retournee(self, monkeypatch):
        final = "https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"
        self._pages(monkeypatch, {"https://doi.org/10.1002/brb3.244": (final, b"<html></html>")})
        svc = self._svc()

        assert asyncio.run(svc._resolve("https://doi.org/10.1002/brb3.244")) == final

    def test_une_resolution_impossible_laisse_l_url_intacte(self, monkeypatch):
        """`doi.org` limite lui aussi les rafales -- constate en mesurant. Un
        refus de sa part ne doit ni faire echouer la source ni la faire sonder
        sur une URL inventee."""
        self._pages(monkeypatch, {})
        svc = self._svc()

        assert asyncio.run(svc._resolve("https://doi.org/10.1002/brb3.244")) == (
            "https://doi.org/10.1002/brb3.244"
        )


class TestUneRedirectionResteUneRedirection:
    """Peu importe comment elle est exprimee.

    Constate en prod le 2026-08-04 : `linkinghub.elsevier.com` repond **200**
    -- aucun client HTTP n'y voit une redirection -- avec un
    `<meta http-equiv="refresh">` vers ScienceDirect et, pour tout contenu, le
    mot « Redirecting ». Seize sources avaient ainsi ete marquees `archived`
    sur un instantane qui ne preserve rien. Verifie en lisant l'instantane :
    9,5 ko de HTML, un seul mot de texte.
    """

    def _svc(self) -> wb.WaybackService:
        return wb.WaybackService(_FakeDb(), None)  # type: ignore[arg-type]

    def _pages(self, monkeypatch, pages):
        TestLaResolutionNeConclutJamais._pages(self, monkeypatch, pages)  # type: ignore[arg-type]

    def test_un_meta_refresh_est_suivi(self, monkeypatch):
        hub = "https://linkinghub.elsevier.com/retrieve/pii/S1388245701006010"
        article = "https://www.sciencedirect.com/science/article/pii/S1388245701006010"
        self._pages(
            monkeypatch,
            {
                hub: (
                    hub,
                    b'<meta HTTP-EQUIV="REFRESH" content="2; url=\'' + article.encode() + b"'\"/>",
                ),
                article: (article, b"<html>le contenu</html>"),
            },
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve(hub)) == article

    def test_une_cible_relative_est_resolue_contre_la_page(self, monkeypatch):
        hub = "https://exemple.org/retrieve/pii/X"
        suite = "https://exemple.org/select?to=X"
        self._pages(
            monkeypatch,
            {
                hub: (hub, b'<meta http-equiv=refresh content="0; url=/select?to=X">'),
                suite: (suite, b"<html>fin</html>"),
            },
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve(hub)) == suite

    def test_une_boucle_de_redirection_ne_tourne_pas_indefiniment(self, monkeypatch):
        a, b = "https://exemple.org/a", "https://exemple.org/b"
        self._pages(
            monkeypatch,
            {
                a: (a, b'<meta http-equiv="refresh" content="0; url=https://exemple.org/b">'),
                b: (b, b'<meta http-equiv="refresh" content="0; url=https://exemple.org/a">'),
            },
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve(a)) in (a, b)

    def test_une_page_sans_meta_refresh_est_la_destination(self, monkeypatch):
        """Tout ne doit pas devenir une redirection : un `<meta>` quelconque
        dans une vraie page d'article ne doit pas deplacer la cible."""
        page = "https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"
        self._pages(
            monkeypatch,
            {page: (page, b'<meta name="citation_title" content="0; url=piege">')},
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve(page)) == page

    def test_une_entite_html_ne_tronque_pas_la_cible(self, monkeypatch):
        """`&amp;` contient un point-virgule. L'exclure de l'URL coupait la
        cible en plein milieu de l'entite : constate en prod le 2026-08-04,
        la resolution rendait `...sciencedirect.com%2F&` sans le parametre
        `key`, et la chaine s'arretait sur une page intermediaire."""
        hub = "https://linkinghub.elsevier.com/retrieve/pii/X"
        suite = "https://linkinghub.elsevier.com/select?Redirect=cible&key=7ced"
        self._pages(
            monkeypatch,
            {
                hub: (
                    hub,
                    b'<meta HTTP-EQUIV="REFRESH" content="2; '
                    b"url='/select?Redirect=cible&amp;key=7ced'\"/>",
                ),
                suite: (suite, b"<html>article</html>"),
            },
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve(hub)) == suite
