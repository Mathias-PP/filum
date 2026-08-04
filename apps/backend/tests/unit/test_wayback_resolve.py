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

    def _client(self, monkeypatch, handler):
        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def head(self, url, **k):
                return handler(url)

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

    def test_la_cible_finale_est_retournee(self, monkeypatch):
        final = "https://onlinelibrary.wiley.com/doi/10.1002/brb3.244"
        self._client(
            monkeypatch,
            lambda url: httpx.Response(200, request=httpx.Request("HEAD", final)),
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve("https://doi.org/10.1002/brb3.244")) == final

    def test_un_403_sur_la_cible_reste_une_resolution_valable(self, monkeypatch):
        """Le cas reel : les editeurs refusent les robots, mais la redirection
        a deja eu lieu -- l'URL finale est connue et c'est tout ce qu'on
        demandait. Juger la resolution sur le code de reponse jetterait une
        information exacte."""
        final = "https://www.annualreviews.org/doi/10.1146/annurev.neuro.24.1.167"
        self._client(
            monkeypatch,
            lambda url: httpx.Response(403, request=httpx.Request("HEAD", final)),
        )
        svc = self._svc()

        assert asyncio.run(svc._resolve("https://doi.org/10.1146/annurev.neuro.24.1.167")) == final

    def test_une_resolution_impossible_laisse_l_url_intacte(self, monkeypatch):
        """`doi.org` limite lui aussi les rafales -- constate en mesurant. Un
        refus de sa part ne doit ni faire echouer la source ni la faire sonder
        sur une URL inventee."""

        def _boom(url):
            raise httpx.ReadTimeout("")

        self._client(monkeypatch, _boom)
        svc = self._svc()

        assert asyncio.run(svc._resolve("https://doi.org/10.1002/brb3.244")) == (
            "https://doi.org/10.1002/brb3.244"
        )
