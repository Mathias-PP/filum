"""Archivage d'un lot : cadence tenable et absence definitive distinguee d'un retard.

Vecu en prod (aout 2026) : une fiche de 152 sources est repartie avec 101
`failed` et 51 `pending`, zero archivee. Save Page Now est limite a quelques
requetes par minute pour un client anonyme ; 152 declenchements simultanes
sont jetes, les 33 s de sondage expirent, et chaque source est inscrite
`failed` -- un etat terminal alors que rien ne prouve que l'URL soit
inarchivable.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.source import ArchiveStatus
from app.services import wayback as wb


class _FakeDb:
    """Collecte les ecritures sans toucher a une base."""

    def __init__(self) -> None:
        self.writes: list[tuple] = []


class _Recorder(wb.WaybackService):
    """Enregistre les appels reseau au lieu de les emettre."""

    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.triggered: list[str] = []
        self.polled: list[str] = []
        self.snapshots: dict[str, str] = {}
        self.written: list[tuple] = []

    async def _trigger_save(self, url: str) -> None:
        self.triggered.append(url)

    async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
        self.polled.append(url)
        snap = self.snapshots.get(url)
        return (snap, "20260804120000") if snap else None

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


@pytest.fixture
def no_sleep(monkeypatch):
    """Les cadences sont testees par leur presence, pas en temps reel."""
    slept: list[float] = []

    async def _sleep(d: float) -> None:
        slept.append(d)

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)
    return slept


class TestCadence:
    def test_un_lot_espace_ses_declenchements(self, no_sleep):
        """Sans espacement, Save Page Now jette le lot entier."""
        svc = _Recorder()
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(5)]

        import asyncio

        asyncio.run(svc.archive_batch(pairs))

        assert svc.triggered == [u for _, u in pairs]
        # Une pause d'au moins la cadence nominale separe deux declenchements.
        assert sum(1 for d in no_sleep if d >= wb.WaybackService.TRIGGER_GAP) >= len(pairs) - 1

    def test_les_declenchements_precedent_tous_les_sondages(self, no_sleep):
        """Save Page Now travaille en differe : sonder juste apres avoir
        declenche ne laisse pas le temps a l'instantane d'exister. Declencher
        tout le lot d'abord donne aux premieres URLs le temps du lot entier."""
        svc = _Recorder()
        order: list[str] = []
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(3)]

        async def _trigger(url: str) -> None:
            order.append(f"trigger:{url}")

        async def _lookup(url: str):
            order.append(f"poll:{url}")
            return None

        svc._trigger_save = _trigger  # type: ignore[method-assign]
        svc._lookup_snapshot = _lookup  # type: ignore[method-assign]

        import asyncio

        asyncio.run(svc.archive_batch(pairs))

        first_poll = next(i for i, e in enumerate(order) if e.startswith("poll:"))
        last_trigger = max(i for i, e in enumerate(order) if e.startswith("trigger:"))
        assert last_trigger < first_poll


class TestHonneteteDesEtats:
    def test_un_instantane_absent_laisse_la_source_en_attente(self, no_sleep):
        """`failed` est terminal et l'interface n'offre aucune reprise. Le
        reserver aux causes definitives : ne pas trouver d'instantane apres
        quelques secondes ne prouve rien sur l'URL."""
        svc = _Recorder()
        sid = uuid4()

        import asyncio

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        statuses = [s for _, s, _ in svc.written]
        assert ArchiveStatus.FAILED not in statuses

    def test_un_instantane_trouve_marque_archivee(self, no_sleep):
        svc = _Recorder()
        sid = uuid4()
        svc.snapshots["https://example.org/a"] = "https://web.archive.org/web/x"

        import asyncio

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        assert (sid, ArchiveStatus.ARCHIVED, "https://web.archive.org/web/x") in svc.written

    def test_une_url_non_publique_echoue_definitivement(self, no_sleep):
        """Celle-la ne sera jamais archivable : la reessayer indefiniment
        serait un mensonge par omission autant qu'un gaspillage."""
        svc = _Recorder()
        sid = uuid4()

        import asyncio

        asyncio.run(svc.archive_batch([(sid, "http://127.0.0.1:8000/interne")]))

        assert (sid, ArchiveStatus.FAILED, None) in svc.written
        assert svc.triggered == []


class TestOrdonnanceur:
    def test_une_source_deja_en_vol_n_est_pas_replanifiee(self, monkeypatch):
        """Une fiche publique servie en boucle relancerait sinon le meme
        archivage a chaque affichage."""
        spawned: list[list] = []

        class _Noop:
            def add_done_callback(self, cb):
                pass

        async def _coro():
            return None

        monkeypatch.setattr(wb.asyncio, "create_task", lambda coro: (coro.close(), _Noop())[1])
        monkeypatch.setattr(wb, "_run_batch", lambda pairs: spawned.append(pairs) or _coro())

        sid = uuid4()
        wb.schedule_archiving([(sid, "https://example.org/a")])
        wb.schedule_archiving([(sid, "https://example.org/a")])

        assert len(spawned) == 1
        wb._in_flight.discard(sid)

    def test_liste_vide_ne_planifie_rien(self, monkeypatch):
        called: list[int] = []
        monkeypatch.setattr(wb.asyncio, "create_task", lambda coro: called.append(1))
        wb.schedule_archiving([])
        assert called == []
