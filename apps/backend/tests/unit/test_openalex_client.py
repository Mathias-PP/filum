"""Tous les appels a OpenAlex portent la cle d'API quand elle est posee.

Depuis le 2026-02-13, OpenAlex exige une cle : sans elle, 100 credits par jour.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.extractors import open_access, openalex_metadonnees
from app.extractors.openalex_client import parametres_openalex


def test_sans_cle_aucun_parametre(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", "")
    assert parametres_openalex() == {}


def test_avec_cle_le_parametre_est_pose(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", " cle-test ")
    assert parametres_openalex() == {"api_key": "cle-test"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "appel",
    [
        lambda: open_access.check_open_access("10.1000/x"),
        lambda: openalex_metadonnees.chercher_par_doi("10.1000/x"),
    ],
)
async def test_chaque_appel_porte_la_cle(monkeypatch, appel):
    vues: list[httpx.URL] = []
    vrai_client = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda requete: vues.append(requete.url) or httpx.Response(404)
        )
        return vrai_client(*args, **kwargs)

    monkeypatch.setattr(get_settings(), "openalex_api_key", "cle-test")
    monkeypatch.setattr(httpx, "AsyncClient", client)
    await appel()
    assert vues and vues[0].params.get("api_key") == "cle-test"
