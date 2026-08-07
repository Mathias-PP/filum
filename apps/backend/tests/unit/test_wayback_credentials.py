"""La cle archive.org doit servir la ou la limite mord, et nulle part ailleurs.

Mesure du 2026-08-07 sur le corpus publie : **493 sources sur 931 en attente**.
Un echantillon de 60 d'entre elles n'avait *aucune* capture dans l'index -- le
travail n'a donc pas ete perdu par une file en memoire, et aucune capture
existante n'a ete manquee. En interrogeant Save Page Now directement, la cause
apparait seule : `429`, y compris sur `example.com`. Le declenchement est
refuse avant d'avoir commence.

Deux defauts se cumulaient.

1. `wayback_api_key` n'etait envoyee qu'au **sondage**, en parametre d'URL. Ce
   n'est pas un mecanisme d'authentification d'archive.org, et le declenchement
   -- le seul appel reellement limite -- restait anonyme. Ouvrir un compte
   n'aurait donc rien change. Le mecanisme documente est l'en-tete
   `Authorization: LOW <access>:<secret>`, les cles s'obtenant sur
   `archive.org/account/s3.php`.

2. Un parametre d'URL se retrouve dans les journaux de qui le recoit. Y mettre
   un secret le divulgue ; l'en-tete est aussi la reponse a cela.

Ce que la cle ne fait pas : elle ne se verifie pas ici. Sans compte
archive.org, ces tests etablissent que la requete est *formee* comme la
documentation le demande, pas que le quota se leve.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services import wayback as wb


class _FakeDb:
    pass


def _espionne(monkeypatch, appels: list[tuple[str, dict]]) -> None:
    """Consigne (url, en-tetes) de chaque requete et repond 200 vide."""

    class _Client:
        def __init__(self, *a, **k) -> None:
            self._headers = k.get("headers") or {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a) -> None:
            return None

        async def get(self, url: str, **k):
            entetes = {**self._headers, **(k.get("headers") or {})}
            appels.append((url + _suffixe(k.get("params")), entetes))
            return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(wb.httpx, "AsyncClient", _Client)


def _suffixe(params: dict | None) -> str:
    return "?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""


def _svc(cle: str | None) -> wb.WaybackService:
    return wb.WaybackService(_FakeDb(), cle)  # type: ignore[arg-type]


def test_declenchement_porte_l_entete_d_autorisation(monkeypatch) -> None:
    appels: list[tuple[str, dict]] = []
    _espionne(monkeypatch, appels)

    asyncio.run(_svc("MaCle:MonSecret")._trigger_save("https://exemple.test/a"))

    assert appels, "le declenchement doit avoir eu lieu"
    _, entetes = appels[0]
    assert entetes.get("Authorization") == "LOW MaCle:MonSecret"


def test_sans_cle_aucune_autorisation(monkeypatch) -> None:
    appels: list[tuple[str, dict]] = []
    _espionne(monkeypatch, appels)

    asyncio.run(_svc(None)._trigger_save("https://exemple.test/a"))

    assert appels
    assert "Authorization" not in appels[0][1]


def test_le_secret_ne_part_jamais_en_parametre_d_url(monkeypatch) -> None:
    """Un parametre d'URL est journalise par le destinataire ; un secret non."""
    appels: list[tuple[str, dict]] = []
    _espionne(monkeypatch, appels)

    svc = _svc("MaCle:MonSecret")
    asyncio.run(svc._trigger_save("https://exemple.test/a"))
    asyncio.run(svc._lookup_via_availability("https://exemple.test/a"))

    for url, _ in appels:
        assert "MonSecret" not in url


def test_sondage_authentifie_aussi(monkeypatch) -> None:
    """Le sondage est limite separement : la cle y sert, mais par en-tete."""
    appels: list[tuple[str, dict]] = []
    _espionne(monkeypatch, appels)

    asyncio.run(_svc("MaCle:MonSecret")._lookup_via_availability("https://exemple.test/a"))

    assert appels
    assert appels[0][1].get("Authorization") == "LOW MaCle:MonSecret"


@pytest.mark.parametrize(
    ("cle", "attendu"),
    [
        (None, wb.WaybackService.TRIGGER_GAP_ANONYME),
        ("", wb.WaybackService.TRIGGER_GAP_ANONYME),
        ("MaCle:MonSecret", wb.WaybackService.TRIGGER_GAP_AUTHENTIFIE),
    ],
)
def test_la_cadence_suit_la_limite_annoncee(cle: str | None, attendu: float) -> None:
    """3 captures/minute en anonyme, 6 avec un compte : 20 s et 10 s.

    Le plancher etait a 6 s, soit 10 par minute -- au-dela meme de ce qu'un
    compte autorise. Demander plus vite que la limite ne rend rien plus
    rapide : cela transforme chaque demande en refus.
    """
    assert _svc(cle)._trigger_gap() == attendu


def test_les_planchers_respectent_la_limite_documentee() -> None:
    assert wb.WaybackService.TRIGGER_GAP_ANONYME >= 60.0 / 3
    assert wb.WaybackService.TRIGGER_GAP_AUTHENTIFIE >= 60.0 / 6
