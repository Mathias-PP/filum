"""« Le service a essaye et echoue » n'est pas « le service refuse de repondre ».

Mesure en prod le 2026-08-04, apres #271. Le tour de role a debloque le
sondage -- 130 -> 125 en attente, 18 -> 23 archivees -- puis tout s'est fige
a 10:09. La phase 2 du lot, celle qui demande une capture, venait de demarrer
et **toutes ses requetes repondaient 520**. Le service reessayait alors la
meme URL en doublant l'attente : 19 s, 30 s, 56 s, 102 s, 127 s... soit les
900 s du budget brules sur **sept requetes et deux URL**.

J'ai lu le corps de ces 520 depuis la VM. Ce ne sont pas des refus de service,
et ils ne disent meme pas tous la meme chose :

- `example.com` -> « This URL has been already captured 5 times today, which
  is a daily limit we have set for that Resource type. Please try again
  tomorrow. »
- `sciencedirect.com/.../S1053811901910468?via%3Dihub` -> « Job failed » --
  archive.org a essaye et n'a pas pu capturer. Coherent avec nos propres
  journaux : ScienceDirect repond `403` aux robots, y compris au sien.

Dans les deux cas le service **s'est prononce sur cette URL**. Redemander la
meme deux minutes plus tard ne peut rien y changer -- et sur le cas du quota,
ce sont nos propres reessais qui le consomment.

Le remede ne lit aucune prose HTML (fragile, et le message peut changer) et
n'etablit aucune liste de domaines : seuls les codes qui disent « reviens plus
tard » ralentissent la cadence. Tout autre code est une reponse au sujet de
cette URL, si malheureuse soit-elle.

⚠️ Le chemin de **sondage** garde son comportement : la un `5xx` reste une
absence de reponse, jamais une absence d'instantane. Confondre les deux etait
le bug de #262 et ne doit pas revenir par cette porte.
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


def _svc() -> wb.WaybackService:
    return wb.WaybackService(_FakeDb(), None)  # type: ignore[arg-type]


def _response(status: int, url: str = "https://web.archive.org/save/x") -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", url))


def _reply(monkeypatch, status: int, seen: list[str]) -> None:
    """Toute requete HTTP repond `status`, et l'URL demandee est consignee."""

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a) -> None:
            return None

        async def get(self, url: str, **k):
            seen.append(url)
            return _response(status, url)

    monkeypatch.setattr(wb.httpx, "AsyncClient", _Client)


@pytest.fixture
def horloge(monkeypatch):
    t = {"v": 0.0}

    async def _sleep(d: float) -> None:
        t["v"] += d

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)
    monkeypatch.setattr(wb.time, "monotonic", lambda: t["v"])
    return t


class TestUnEchecDeCaptureNEstPasUnRefus:
    def test_un_520_ne_ralentit_pas_la_cadence(self, monkeypatch):
        """Le coeur du bug : `ThrottledError` est ce qui double l'attente."""
        seen: list[str] = []
        _reply(monkeypatch, 520, seen)

        asyncio.run(_svc()._trigger_save("https://example.org/a"))

        assert seen  # la requete a bien ete faite
        # Aucune exception : le service s'est prononce, on passe a la suivante.

    @pytest.mark.parametrize("code", [429, 503, 523])
    def test_un_vrai_refus_reste_un_refus(self, monkeypatch, code):
        """429 est explicite ; 503 et 523 (origine injoignable, mesure en
        aout 2026) disent la meme chose : reviens plus tard."""
        seen: list[str] = []
        _reply(monkeypatch, code, seen)

        with pytest.raises(wb.ThrottledError):
            asyncio.run(_svc()._trigger_save("https://example.org/a"))

    @pytest.mark.parametrize("code", [500, 502, 504, 520])
    def test_les_autres_erreurs_sont_des_reponses_sur_cette_url(self, monkeypatch, code):
        """Insister ne peut rien y changer : la capture a ete jugee."""
        seen: list[str] = []
        _reply(monkeypatch, code, seen)

        asyncio.run(_svc()._trigger_save("https://example.org/a"))

    def test_un_succes_ne_leve_rien(self, monkeypatch):
        seen: list[str] = []
        _reply(monkeypatch, 200, seen)

        asyncio.run(_svc()._trigger_save("https://example.org/a"))


class _Recorder(wb.WaybackService):
    """Un service dont seule la couche HTTP est simulee."""

    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.written: list[tuple] = []

    async def _mark_attempted(self, source_id) -> None:  # type: ignore[override]
        return None

    async def _resolve(self, url: str) -> str:
        return url

    async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
        return None

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


class TestLeBudgetNEstPasBruleSurUneSeuleUrl:
    def test_une_capture_jugee_impossible_n_est_demandee_qu_une_fois(self, horloge, monkeypatch):
        """Mesure en prod : sept requetes pour deux URL, 900 s de budget.

        Avec un 520 par URL, on doit voir exactement une demande par URL --
        pas `MAX_ATTEMPTS` fois la meme.
        """
        seen: list[str] = []
        _reply(monkeypatch, 520, seen)
        svc = _Recorder()
        pairs = [(uuid4(), f"https://example.org/{i}") for i in range(5)]

        asyncio.run(svc.archive_batch(pairs))

        saves = [u for u in seen if u.startswith(wb.WaybackService.SAVE_URL)]
        assert len(saves) == 5
        assert len(set(saves)) == 5

    def test_un_refus_reel_est_bien_reessaye(self, horloge, monkeypatch):
        """Le garde-fou dans l'autre sens : ne pas transformer ce correctif en
        « on n'insiste plus jamais »."""
        seen: list[str] = []
        _reply(monkeypatch, 429, seen)
        svc = _Recorder()

        asyncio.run(svc.archive_batch([(uuid4(), "https://example.org/a")]))

        saves = [u for u in seen if u.startswith(wb.WaybackService.SAVE_URL)]
        assert len(saves) > 1

    def test_une_capture_impossible_laisse_la_source_en_attente(self, horloge, monkeypatch):
        """Ne pas remplacer un mensonge par un autre : « archive.org n'a pas
        pu capturer aujourd'hui » n'est pas « cette page est perdue »."""
        seen: list[str] = []
        _reply(monkeypatch, 520, seen)
        svc = _Recorder()
        sid = uuid4()

        asyncio.run(svc.archive_batch([(sid, "https://example.org/a")]))

        statuses = [st for _, st, _ in svc.written]
        assert ArchiveStatus.FAILED not in statuses
        assert ArchiveStatus.ARCHIVED not in statuses


class TestLeSondageGardeSesRegles:
    """Regression de #262 : sur le chemin du sondage, un `5xx` reste une
    absence de reponse -- jamais une absence d'instantane."""

    @pytest.mark.parametrize("code", [500, 502, 503, 520, 523, 429])
    def test_un_5xx_au_sondage_ne_conclut_pas(self, monkeypatch, code):
        seen: list[str] = []
        _reply(monkeypatch, code, seen)

        with pytest.raises(wb.ThrottledError):
            asyncio.run(_svc()._lookup_snapshot("https://example.org/a"))
