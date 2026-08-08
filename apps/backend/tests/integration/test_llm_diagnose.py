"""La sonde qui dit si la couche LLM est vivante.

Rien dans l'interface ne distingue « le modele n'a rien trouve » de « il n'y a
pas de modele » : les deux rendent une liste vide. Cette sonde existe pour
lever exactement cette ambiguite, et elle n'a de valeur que si elle repond en
prod — donc sans auth, donc sans jamais rendre la cle.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.services import llm


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_sans_modele_la_sonde_dit_quoi_faire(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "litellm_base_url", "")
    r = await client.get("/health/llm-diagnose")
    assert r.status_code == 200
    corps = r.json()
    assert corps["status"] == "off"
    # Un diagnostic qui constate sans dire quoi corriger ne sert a rien.
    assert "litellm_base_url" in corps["a_faire"]


@pytest.mark.asyncio
async def test_la_sonde_ne_rend_jamais_la_cle(client, monkeypatch):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "litellm_base_url", "https://exemple.test")
    monkeypatch.setattr(reglages, "litellm_master_key", "cle-tres-secrete")
    monkeypatch.setattr(reglages, "llm_direct_model", "un-modele")

    async def rien(*a, **k):
        return None

    monkeypatch.setattr(llm, "suggest_excerpts", rien)
    r = await client.get("/health/llm-diagnose")
    # La sonde est ouverte a tous : la cle ne doit apparaitre nulle part.
    assert "cle-tres-secrete" not in r.text
    assert r.json()["status"] == "erreur"


@pytest.mark.asyncio
async def test_un_alias_non_resolu_est_signale(client, monkeypatch):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "litellm_base_url", "https://exemple.test")
    monkeypatch.setattr(reglages, "llm_direct_model", "")

    async def suggere(*a, **k):
        return ["Un passage."]

    monkeypatch.setattr(llm, "suggest_excerpts", suggere)
    corps = (await client.get("/health/llm-diagnose")).json()
    assert corps["status"] == "ok"
    # Sans proxy, un alias qui reste un alias est la cause la plus probable
    # d'un 404 : le dire evite de chercher du cote de la cle.
    assert corps["alias_non_resolu"] is True
    assert corps["modele_resolu"] == "excerpt-suggest"
