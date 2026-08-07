"""La cadence s'ajuste au service au lieu de la deviner.

Mesure en prod (aout 2026), sur le lot de 152 sources remis en attente par
#257 : Save Page Now repondait `429 TOO MANY REQUESTS` malgre l'intervalle
fixe de 6 s, entrecoupe de `523` (Cloudflare : origine injoignable). L'API de
disponibilite refusait elle aussi les rafales, avec une penalite qui survit
plusieurs minutes. Zero source archivee sur 152.

Deux defauts, un seul principe. D'abord un intervalle fixe ne peut pas etre
juste : les limites d'archive.org ne sont pas publiees et varient avec la
charge, donc toute valeur codee en dur est soit trop lente, soit rejetee.
Ensuite -- et c'est la meme faute que #257, un cran plus bas -- un refus de
service etait indistinguable d'une absence d'instantane : `_lookup_snapshot`
avalait le 429 et repondait « aucun instantane », ce qui conclut sur une URL
qu'on n'a jamais reussi a interroger.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.models.source import ArchiveStatus
from app.services import wayback as wb


class _FakeDb:
    pass


class _Recorder(wb.WaybackService):
    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.triggered: list[str] = []
        self.polled: list[str] = []
        self.written: list[tuple] = []
        self.trigger_throttles = 0
        self.lookup_throttles = 0
        self.snapshots: dict[str, str] = {}

    async def _mark_attempted(self, source_id) -> None:  # type: ignore[override]
        # Pas de base en test unitaire : la tentative n'a rien a dater.
        return None

    async def _resolve(self, url: str) -> str:
        # Aucun reseau en test unitaire : ces URL ne redirigent pas.
        return url

    async def _trigger_save(self, url: str) -> None:
        self.triggered.append(url)
        if self.trigger_throttles > 0:
            self.trigger_throttles -= 1
            raise wb.ThrottledError()

    async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
        self.polled.append(url)
        if self.lookup_throttles > 0:
            self.lookup_throttles -= 1
            raise wb.ThrottledError()
        snap = self.snapshots.get(url)
        return (snap, "20260804120000") if snap else None

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


@pytest.fixture
def slept(monkeypatch):
    """Les pauses sont observees, pas subies.

    L'horloge du service suit ces pauses simulees : le budget d'un lot se
    mesure en temps ecoule, et une horloge figee le rendrait inatteignable.
    """
    out: list[float] = []
    horloge = {"t": 0.0}

    async def _sleep(d: float) -> None:
        out.append(d)
        horloge["t"] += d

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)
    monkeypatch.setattr(wb.time, "monotonic", lambda: horloge["t"])
    return out


def _run(svc, pairs):
    return asyncio.run(svc.archive_batch(pairs))


class TestLeRefusEstUnSignal:
    def test_un_429_au_sondage_ne_vaut_pas_absence_d_instantane(self, slept):
        """Le coeur du bug : conclure « pas d'instantane » sur une requete que
        le service a refusee, c'est conclure sans avoir regarde."""
        svc = _Recorder()
        sid = uuid4()
        svc.lookup_throttles = 1
        svc.snapshots["https://example.org/a"] = "https://web.archive.org/web/x"

        _run(svc, [(sid, "https://example.org/a")])

        assert (sid, ArchiveStatus.ARCHIVED, "https://web.archive.org/web/x") in svc.written

    def test_un_refus_ralentit_la_cadence(self, slept):
        svc = _Recorder()
        svc.trigger_throttles = 2

        _run(svc, [(uuid4(), "https://example.org/a")])

        assert max(slept) > wb.WaybackService.TRIGGER_GAP_ANONYME

    def test_un_refus_au_declenchement_est_reessaye(self, slept):
        svc = _Recorder()
        svc.trigger_throttles = 1

        _run(svc, [(uuid4(), "https://example.org/a")])

        assert svc.triggered.count("https://example.org/a") == 2

    def test_l_acharnement_est_borne(self, slept):
        """Un service durablement indisponible ne doit pas etre pilonne."""
        svc = _Recorder()
        svc.trigger_throttles = 10_000

        _run(svc, [(uuid4(), "https://example.org/a")])

        assert svc.triggered.count("https://example.org/a") <= wb.WaybackService.MAX_ATTEMPTS

    def test_une_source_jamais_interrogee_reste_en_attente(self, slept):
        """Ni archivee (on n'a rien vu) ni en echec (on n'a rien juge)."""
        svc = _Recorder()
        sid = uuid4()
        svc.trigger_throttles = 10_000
        svc.lookup_throttles = 10_000

        _run(svc, [(sid, "https://example.org/a")])

        statuses = [st for _, st, _ in svc.written]
        assert ArchiveStatus.FAILED not in statuses
        assert ArchiveStatus.ARCHIVED not in statuses


class TestBudget:
    def test_un_lot_ne_tourne_pas_indefiniment(self, slept):
        """La cadence peut monter tres haut ; sans plafond de temps, un lot de
        152 sources tiendrait la connexion a la base pendant des heures. Ce qui
        depasse reste en attente, et la reprise paresseuse le reproposera."""
        svc = _Recorder()
        svc.trigger_throttles = 10_000
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(200)]

        _run(svc, pairs)

        assert sum(slept) <= wb.WaybackService.BATCH_BUDGET * 2

    def test_le_travail_non_fait_reste_en_attente(self, slept):
        svc = _Recorder()
        svc.trigger_throttles = 10_000
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(200)]

        _run(svc, pairs)

        assert all(st != ArchiveStatus.FAILED for _, st, _ in svc.written)


class TestLectureDuRefus:
    """`_lookup_snapshot` doit reconnaitre un refus dans la reponse HTTP."""

    def _svc(self) -> wb.WaybackService:
        return wb.WaybackService(_FakeDb(), None)  # type: ignore[arg-type]

    def test_un_429_leve_throttled(self, monkeypatch):
        svc = self._svc()

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return httpx.Response(429, request=httpx.Request("GET", "https://archive.org"))

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

        with pytest.raises(wb.ThrottledError):
            asyncio.run(svc._lookup_snapshot("https://example.org/a"))

    def test_un_retry_after_est_honore(self, monkeypatch):
        svc = self._svc()

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return httpx.Response(
                    429,
                    headers={"retry-after": "45"},
                    request=httpx.Request("GET", "https://archive.org"),
                )

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

        with pytest.raises(wb.ThrottledError) as exc:
            asyncio.run(svc._lookup_snapshot("https://example.org/a"))
        assert exc.value.retry_after == 45.0

    def test_une_reponse_saine_sans_instantane_reste_une_absence(self, monkeypatch):
        """Tout ne doit pas devenir un refus : quand le service repond
        normalement qu'il n'a rien, c'est bien une absence."""
        svc = self._svc()

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return httpx.Response(
                    200,
                    json={"archived_snapshots": {}},
                    request=httpx.Request("GET", "https://archive.org"),
                )

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

        assert asyncio.run(svc._lookup_snapshot("https://example.org/a")) is None
