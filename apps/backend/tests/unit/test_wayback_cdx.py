"""Un canal qui refuse ne conclut pas : il en reste un autre.

Mesure depuis la VM le 2026-08-04, a la meme seconde et depuis la meme IP :

    archive.org/wayback/available?url=...        -> 429
    web.archive.org/cdx/search/cdx?url=...       -> 200, instantane trouve

Les deux interrogent le meme index. La limitation porte sur le point d'entree,
pas sur l'archive. Conclure « aucun instantane » parce que le premier canal
nous a ete ferme, c'est la faute corrigee une couche plus haut : conclure sans
avoir regarde.

D'ou la regle, qui vaut au-dela de ces deux URL : on n'affirme une absence que
si un canal a repondu sainement. Si tous refusent, on ne sait pas, et la source
reste en attente.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services import wayback as wb


class _FakeDb:
    pass


def _svc() -> wb.WaybackService:
    return wb.WaybackService(_FakeDb(), None)  # type: ignore[arg-type]


def _client_returning(by_host):
    """Un client HTTP qui repond selon l'hote interroge."""

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **kwargs):
            for fragment, make in by_host.items():
                if fragment in url:
                    return make(url)
            raise AssertionError(f"URL inattendue : {url}")

    return lambda **k: _Client()


def _ok_cdx(rows):
    return lambda url: httpx.Response(
        200, json=rows, request=httpx.Request("GET", "https://web.archive.org")
    )


def _refused(url):
    return httpx.Response(429, request=httpx.Request("GET", "https://archive.org"))


_CDX_HIT = [
    ["timestamp", "original"],
    ["20221110000958", "https://www.frontiersin.org/articles/10.3389/fpsyg.2022.651547/full"],
]


class TestSecondCanal:
    def test_un_refus_du_premier_canal_n_empeche_pas_de_trouver(self, monkeypatch):
        """Le cas mesure en prod : availability limite, CDX disponible."""
        monkeypatch.setattr(
            wb.httpx,
            "AsyncClient",
            _client_returning({"wayback/available": _refused, "cdx/search": _ok_cdx(_CDX_HIT)}),
        )

        found = asyncio.run(_svc()._lookup_snapshot("https://example.org/a"))

        assert found is not None
        archive_url, timestamp = found
        assert "20221110000958" in archive_url
        assert timestamp == "20221110000958"

    def test_une_absence_confirmee_par_un_canal_sain_reste_une_absence(self, monkeypatch):
        """CDX repond, et repond qu'il n'a rien. C'est une reponse, pas un refus."""
        monkeypatch.setattr(
            wb.httpx,
            "AsyncClient",
            _client_returning({"wayback/available": _refused, "cdx/search": _ok_cdx([])}),
        )

        assert asyncio.run(_svc()._lookup_snapshot("https://example.org/a")) is None

    def test_tous_les_canaux_refuses_ne_conclut_pas(self, monkeypatch):
        monkeypatch.setattr(
            wb.httpx,
            "AsyncClient",
            _client_returning({"wayback/available": _refused, "cdx/search": _refused}),
        )

        with pytest.raises(wb.ThrottledError):
            asyncio.run(_svc()._lookup_snapshot("https://example.org/a"))

    def test_une_reponse_cdx_illisible_ne_vaut_pas_absence(self, monkeypatch):
        """CDX renvoie parfois du HTML d'erreur avec un code 200. Ce n'est pas
        une reponse exploitable : on laisse l'autre canal se prononcer."""
        monkeypatch.setattr(
            wb.httpx,
            "AsyncClient",
            _client_returning(
                {
                    "cdx/search": lambda url: httpx.Response(
                        200,
                        text="<html>oops</html>",
                        request=httpx.Request("GET", "https://web.archive.org"),
                    ),
                    "wayback/available": lambda url: httpx.Response(
                        200,
                        json={
                            "archived_snapshots": {
                                "closest": {
                                    "url": "https://web.archive.org/web/2020/x",
                                    "timestamp": "20200101000000",
                                }
                            }
                        },
                        request=httpx.Request("GET", "https://archive.org"),
                    ),
                }
            ),
        )

        found = asyncio.run(_svc()._lookup_snapshot("https://example.org/a"))

        assert found == ("https://web.archive.org/web/2020/x", "20200101000000")

    def test_l_entete_seule_ne_passe_pas_pour_un_instantane(self, monkeypatch):
        """CDX renvoie la ligne d'en-tetes meme quand il n'a aucun resultat."""
        monkeypatch.setattr(
            wb.httpx,
            "AsyncClient",
            _client_returning(
                {
                    "cdx/search": _ok_cdx([["timestamp", "original"]]),
                    "wayback/available": _ok_cdx({"archived_snapshots": {}}),
                }
            ),
        )

        assert asyncio.run(_svc()._lookup_snapshot("https://example.org/a")) is None


class TestPatienceDuSondage:
    """CDX cherche dans un index de centaines de milliards de captures.

    Mesure depuis la VM le 2026-08-04, trois appels de suite : **18,4 s,
    18,7 s, 19,7 s** pour une requete qui ne renvoie rien. Le delai de 30 s
    partage avec le reste du service etait donc depasse des que la machine
    etait chargee -- et le sondage echouait sur un timeout dont le message est
    vide, ce qui rendait le diagnostic muet.
    """

    def test_le_sondage_a_son_propre_delai_plus_genereux(self, monkeypatch):
        vus: list[float] = []

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return httpx.Response(
                    200, json=[], request=httpx.Request("GET", "https://web.archive.org")
                )

        def _factory(**kwargs):
            vus.append(kwargs.get("timeout"))
            return _Client()

        monkeypatch.setattr(wb.httpx, "AsyncClient", _factory)

        asyncio.run(_svc()._lookup_via_cdx("https://example.org/a"))

        assert vus and vus[0] >= 3 * 19.7

    def test_le_type_de_la_panne_est_journalise(self, monkeypatch, caplog):
        """Un timeout de lecture a un message vide : sans son type, le journal
        n'apprend rien a qui cherche la cause."""

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                raise httpx.ReadTimeout("")

        monkeypatch.setattr(wb.httpx, "AsyncClient", lambda **k: _Client())

        with caplog.at_level("INFO"), pytest.raises(wb.ThrottledError):
            asyncio.run(_svc()._lookup_via_cdx("https://example.org/a"))

        assert "ReadTimeout" in caplog.text
