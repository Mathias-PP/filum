"""Une source jamais atteinte n'est pas « en attente », elle est ignoree.

Mesure en prod le 2026-08-04, apres #268, #269 et #270 : la fiche restait a
**132 en attente** malgre six passes de reprise. Le lot les parcourait
pourtant, et le journal montrait des reponses CDX saines.

La cause n'etait ni la resolution ni la cadence : `cards.py` construisait la
liste des `pending` **toujours dans le meme ordre**, et le lot s'arretait sur
son budget. Les sources situees apres la frontiere n'etaient donc **jamais
atteintes** -- pas une fois, jamais. Verifie en resolvant un echantillon a la
main : `10.3389/fnsys.2014.00206` et `10.3389/fnhum.2017.00020` ont une
capture `200` disponible a l'instant meme, et restaient `pending`.

C'est la meme faute que le reste de la serie, une couche plus haut : `pending`
disait « en cours de traitement » pour des sources que personne ne traitait.
Le remede est de rendre l'etat vrai -- consigner **quand une source a ete
tentee**, et servir en premier celles qui l'ont ete le moins recemment.

`archive_attempted_at` (quand on a essaye) et `archive_timestamp` (quand la
capture a ete faite) sont deux faits distincts : les confondre reintroduirait
exactement l'erreur que toute cette serie corrige.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.models.source import ArchiveStatus
from app.services import wayback as wb


class _FakeDb:
    pass


class _Recorder(wb.WaybackService):
    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.attempted: list = []
        self.written: list[tuple] = []
        self.snapshots: dict[str, str] = {}
        self.lookup_throttles = 0

    async def _resolve(self, url: str) -> str:
        # Aucun reseau en test unitaire : ces URL ne redirigent pas.
        return url

    async def _trigger_save(self, url: str) -> None:
        return None

    async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
        if self.lookup_throttles > 0:
            self.lookup_throttles -= 1
            raise wb.ThrottledError()
        snap = self.snapshots.get(url)
        return (snap, "20260804120000") if snap else None

    async def _mark_attempted(self, source_id) -> None:  # type: ignore[override]
        self.attempted.append(source_id)

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


@pytest.fixture
def horloge(monkeypatch):
    """Les pauses sont observees, et l'horloge du service les suit."""
    t = {"v": 0.0}

    async def _sleep(d: float) -> None:
        t["v"] += d

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)
    monkeypatch.setattr(wb.time, "monotonic", lambda: t["v"])
    return t


class TestUneTentativeEstConsignee:
    def test_une_source_atteinte_est_marquee_comme_tentee(self, horloge):
        svc = _Recorder()
        sid = uuid4()

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        assert sid in svc.attempted

    def test_marquer_une_tentative_ne_conclut_rien(self, horloge):
        """Avoir essaye n'est ni un succes ni un echec."""
        svc = _Recorder()
        sid = uuid4()

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        statuses = [st for _, st, _ in svc.written]
        assert ArchiveStatus.ARCHIVED not in statuses
        assert ArchiveStatus.FAILED not in statuses

    def test_une_source_hors_budget_n_est_pas_marquee(self, horloge):
        """Le coeur du bug : sans cette distinction, la queue du lot serait
        indiscernable de ce qui a vraiment ete tente.

        Le budget s'epuise parce que le service refuse -- exactement ce qui
        se passe en prod, ou la cadence recule a chaque `429`.
        """
        svc = _Recorder()
        svc.lookup_throttles = 10_000
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(400)]

        asyncio.run(svc.archive_batch(pairs))

        assert 0 < len(svc.attempted) < len(pairs)

    def test_une_source_sans_url_n_est_pas_une_tentative(self, horloge):
        """Il n'y a rien a tenter : la source est classee sans reseau."""
        svc = _Recorder()
        sid = uuid4()

        asyncio.run(svc.archive_batch([(sid, "   ")]))

        assert svc.attempted == []
        assert (sid, ArchiveStatus.NOT_APPLICABLE, None) in svc.written


class _Src:
    def __init__(self, name: str, attempted: datetime | None) -> None:
        self.name = name
        self.archive_attempted_at = attempted


class TestLeTourDeRole:
    """Servir en premier ce qui a ete tente le moins recemment."""

    def test_une_source_jamais_tentee_passe_en_premier(self):
        recente = _Src("recente", datetime(2026, 8, 4, 12, 0))
        jamais = _Src("jamais", None)

        ordre = wb.least_recently_attempted([recente, jamais])

        assert [s.name for s in ordre] == ["jamais", "recente"]

    def test_la_plus_ancienne_tentative_passe_avant_la_plus_recente(self):
        vieille = _Src("vieille", datetime(2026, 8, 1, 9, 0))
        fraiche = _Src("fraiche", datetime(2026, 8, 4, 9, 0))

        ordre = wb.least_recently_attempted([fraiche, vieille])

        assert [s.name for s in ordre] == ["vieille", "fraiche"]

    def test_la_queue_finit_par_passer_en_tete(self):
        """La propriete qui compte : ce qu'une passe n'a pas atteint est
        servi en premier a la suivante. Sans elle, la queue d'un lot
        budgete n'est jamais traitee -- pas « plus tard », jamais."""
        base = datetime(2026, 8, 4, 12, 0)
        sources = [_Src(f"s{i}", None) for i in range(10)]

        # Premiere passe : le budget n'en atteint que trois.
        ordre = wb.least_recently_attempted(sources)
        for i, s in enumerate(ordre[:3]):
            s.archive_attempted_at = base + timedelta(seconds=i)

        suivante = wb.least_recently_attempted(sources)

        assert [s.name for s in suivante[:3]] == ["s3", "s4", "s5"]
        assert [s.name for s in suivante[-3:]] == ["s0", "s1", "s2"]

    def test_l_ordre_est_stable_a_tentatives_egales(self):
        """Rien ne justifierait de brasser des sources equivalentes."""
        a, b, c = _Src("a", None), _Src("b", None), _Src("c", None)

        assert [s.name for s in wb.least_recently_attempted([a, b, c])] == ["a", "b", "c"]
