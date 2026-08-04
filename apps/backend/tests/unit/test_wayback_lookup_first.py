"""Regarder avant de demander, et compter le temps qui passe.

Constate en prod le 2026-08-04, apres #262 et #265 : la fiche de 152 sources
restait a zero archivee alors que le sondage, execute a la main dans le
conteneur, trouvait immediatement l'instantane de la premiere URL essayee.

Deux defauts, tous deux invisibles en test tant qu'on ne mesurait que les
pauses.

1. **On demandait une capture avant de regarder s'il en existait une.** Le lot
   declenchait Save Page Now pour les 152 URL, puis sondait. Or une bonne part
   d'entre elles etaient deja dans l'archive depuis des annees. On payait donc
   la partie la plus lente et la plus limitee du service pour un travail deja
   fait -- et le budget s'epuisait avant d'avoir rien archive.

2. **Le budget mesurait les pauses, pas le temps ecoule.** Chaque requete peut
   prendre jusqu'a 30 s, et chaque URL refusee est reessayee. Un lot pouvait
   donc tenir des heures sans jamais « depasser » un budget de 900 s, qui ne
   protegeait pas ce qu'il pretendait proteger.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

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
        self.snapshots: dict[str, str] = {}

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
    async def _sleep(d: float) -> None:
        return None

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)


class TestRegarderAvantDeDemander:
    def test_une_url_deja_archivee_n_est_pas_redemandee(self, no_sleep):
        """Le cas majoritaire d'une bibliographie academique : les articles
        cites sont dans l'archive depuis des annees."""
        svc = _Recorder()
        sid = uuid4()
        svc.snapshots["https://example.org/a"] = "https://web.archive.org/web/2019/a"

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        assert svc.triggered == []
        assert (sid, ArchiveStatus.ARCHIVED, "https://web.archive.org/web/2019/a") in svc.written

    def test_une_url_absente_de_l_archive_est_bien_demandee(self, no_sleep):
        svc = _Recorder()

        asyncio.run(svc.archive_batch([(uuid4(), "https://example.org/neuf")]))

        assert svc.triggered == ["https://example.org/neuf"]

    def test_le_lot_mele_les_deux_cas_sans_se_tromper(self, no_sleep):
        svc = _Recorder()
        vieux, neuf = uuid4(), uuid4()
        svc.snapshots["https://example.org/vieux"] = "https://web.archive.org/web/2019/v"

        asyncio.run(
            svc.archive_batch(
                [(vieux, "https://example.org/vieux"), (neuf, "https://example.org/neuf")]
            )
        )

        assert svc.triggered == ["https://example.org/neuf"]
        statuses = {sid: st for sid, st, _ in svc.written}
        assert statuses[vieux] == ArchiveStatus.ARCHIVED
        assert neuf not in statuses  # ni archivee, ni en echec : en attente.


class TestBudgetEnTempsEcoule:
    def test_le_temps_passe_dans_les_requetes_compte(self, monkeypatch):
        """Sans cela, un service lent tient la session base indefiniment : les
        pauses restent minuscules pendant que les requetes durent 30 s."""
        horloge = {"t": 0.0}
        monkeypatch.setattr(wb.time, "monotonic", lambda: horloge["t"])

        async def _sleep(d: float) -> None:
            horloge["t"] += d

        monkeypatch.setattr(wb.asyncio, "sleep", _sleep)

        class _Lent(_Recorder):
            async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
                self.polled.append(url)
                horloge["t"] += 30.0  # une requete lente, sans aucune pause.
                return None

        svc = _Lent()
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(500)]

        asyncio.run(svc.archive_batch(pairs))

        assert len(svc.polled) < 500
        assert horloge["t"] <= wb.WaybackService.BATCH_BUDGET * 2

    def test_ce_qui_n_a_pas_ete_traite_reste_en_attente(self, monkeypatch):
        horloge = {"t": 0.0}
        monkeypatch.setattr(wb.time, "monotonic", lambda: horloge["t"])

        async def _sleep(d: float) -> None:
            horloge["t"] += d

        monkeypatch.setattr(wb.asyncio, "sleep", _sleep)

        class _Lent(_Recorder):
            async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
                horloge["t"] += 30.0
                return None

        svc = _Lent()
        asyncio.run(svc.archive_batch([(uuid4(), f"https://example.org/{i}") for i in range(500)]))

        assert all(st != ArchiveStatus.FAILED for _, st, _ in svc.written)
