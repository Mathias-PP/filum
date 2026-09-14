"""Le cache des pages lues se borne en caracteres, pas en nombre de pages."""

from __future__ import annotations

import pytest

from app.api.v1.endpoints import excerpts as endpoint
from app.services import excerpt_insertion
from app.services.excerpt_insertion import texte_de_page


@pytest.fixture
def lectures(monkeypatch):
    lues: list[str] = []

    async def source(url):
        lues.append(url)
        return url[-1] * 10, False, True

    monkeypatch.setattr(endpoint, "_texte_de_la_source", source)
    excerpt_insertion.vider_le_cache()
    yield lues
    excerpt_insertion.vider_le_cache()


@pytest.mark.asyncio
async def test_les_plus_anciennes_pages_sortent_quand_le_budget_est_depasse(lectures, monkeypatch):
    monkeypatch.setattr(excerpt_insertion, "_BUDGET_CARACTERES", 25)
    for lettre in "abc":
        await texte_de_page(f"https://a.test/{lettre}")
    await texte_de_page("https://a.test/b")
    await texte_de_page("https://a.test/c")
    assert lectures == ["https://a.test/a", "https://a.test/b", "https://a.test/c"]

    await texte_de_page("https://a.test/a")
    assert lectures[-1] == "https://a.test/a"


@pytest.mark.asyncio
async def test_une_page_plus_grosse_que_le_budget_reste_le_temps_de_sa_pose(lectures, monkeypatch):
    monkeypatch.setattr(excerpt_insertion, "_BUDGET_CARACTERES", 5)
    await texte_de_page("https://a.test/a")
    await texte_de_page("https://a.test/a")
    assert lectures == ["https://a.test/a"]
