"""Tous les appels a OpenAlex portent la cle d'API, et jamais dans l'URL.

Depuis le 2026-02-13, OpenAlex exige une cle. Une cle placee dans l'URL finit
dans les journaux et les messages d'exception : elle part dans l'en-tete.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.extractors import open_access, openalex_metadonnees
from app.extractors.openalex_client import entetes_openalex


def test_sans_cle_aucun_en_tete(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", "")
    assert entetes_openalex() == {}


def test_avec_cle_l_en_tete_est_pose(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", " cle-test ")
    assert entetes_openalex() == {"Authorization": "Bearer cle-test"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "appel",
    [
        lambda: open_access.check_open_access("10.1000/x"),
        lambda: openalex_metadonnees.chercher_par_doi("10.1000/x"),
    ],
)
async def test_chaque_appel_porte_la_cle_hors_de_l_url(monkeypatch, appel):
    vues: list[httpx.Request] = []
    vrai_client = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda requete: vues.append(requete) or httpx.Response(404)
        )
        return vrai_client(*args, **kwargs)

    monkeypatch.setattr(get_settings(), "openalex_api_key", "cle-test")
    monkeypatch.setattr(httpx, "AsyncClient", client)
    await appel()
    assert vues
    assert vues[0].headers.get("Authorization") == "Bearer cle-test"
    assert "cle-test" not in str(vues[0].url)
