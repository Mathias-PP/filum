"""Retry des enrichissements externes (Crossref 2e passe, S2 backoff 429).

Contexte : sur un article a 145 refs, ~10 lookups Crossref echouent de
maniere transitoire (timeout sous concurrence 10) et les trous changent a
chaque run — un retry les recupere tous. Cote Semantic Scholar, le pool
anonyme (100 req / 5 min) renvoie souvent 429 et l'etage sautait
silencieusement sans retry.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints import imports as imports_module
from app.api.v1.endpoints.imports import _backfill_crossref_metadata
from app.extractors import semantic_scholar as s2_module
from app.extractors.semantic_scholar import get_paper_references
from app.extractors.url_extractor import ExtractedMetadata
from app.services.import_parsers import ImportedRef


@pytest.mark.asyncio
async def test_crossref_backfill_retries_transient_failures(monkeypatch):
    """Un lookup qui echoue au 1er appel mais reussit au 2e doit remplir la ref."""
    calls: dict[str, int] = {}

    async def flaky_lookup(doi: str) -> ExtractedMetadata | None:
        calls[doi] = calls.get(doi, 0) + 1
        if calls[doi] == 1:
            return None  # timeout transitoire simule
        return ExtractedMetadata(title=f"Title {doi}", authors="Doe J.", published_at="2020-01-01")

    monkeypatch.setattr(imports_module, "crossref_lookup", flaky_lookup)

    refs = [
        ImportedRef(url="https://doi.org/10.1000/aaa"),
        ImportedRef(url="https://doi.org/10.1000/bbb"),
    ]
    await _backfill_crossref_metadata(refs)

    for ref in refs:
        assert ref.title is not None
        assert ref.authors == "Doe J."
    assert all(count == 2 for count in calls.values())


@pytest.mark.asyncio
async def test_crossref_backfill_gives_up_after_second_pass(monkeypatch):
    """Un lookup qui echoue toujours ne boucle pas indefiniment (2 passes max)."""
    calls: dict[str, int] = {}

    async def dead_lookup(doi: str) -> ExtractedMetadata | None:
        calls[doi] = calls.get(doi, 0) + 1
        return None

    monkeypatch.setattr(imports_module, "crossref_lookup", dead_lookup)

    refs = [ImportedRef(url="https://doi.org/10.1000/dead")]
    await _backfill_crossref_metadata(refs)

    assert refs[0].title is None
    assert calls["10.1000/dead"] == 2


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Simule httpx.AsyncClient : 429 aux N premiers appels puis 200."""

    responses: list[_FakeResponse] = []
    call_count = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url: str):
        cls = type(self)
        cls.call_count += 1
        return cls.responses.pop(0)


@pytest.mark.asyncio
async def test_s2_retries_on_429(monkeypatch):
    ok_payload = {
        "data": [
            {
                "citedPaper": {
                    "title": "Some paper",
                    "authors": [{"name": "Jane Doe"}],
                    "year": 2019,
                    "externalIds": {"DOI": "10.1000/xyz"},
                }
            }
        ]
    }
    _FakeAsyncClient.responses = [_FakeResponse(429), _FakeResponse(200, ok_payload)]
    _FakeAsyncClient.call_count = 0
    monkeypatch.setattr(s2_module.httpx, "AsyncClient", _FakeAsyncClient)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(s2_module.asyncio, "sleep", no_sleep)

    refs = await get_paper_references("10.3389/fpsyg.2022.651547")

    assert _FakeAsyncClient.call_count == 2
    assert refs is not None and len(refs) == 1
    assert refs[0].title == "Some paper"


@pytest.mark.asyncio
async def test_s2_gives_up_after_max_retries(monkeypatch):
    _FakeAsyncClient.responses = [_FakeResponse(429), _FakeResponse(429), _FakeResponse(429)]
    _FakeAsyncClient.call_count = 0
    monkeypatch.setattr(s2_module.httpx, "AsyncClient", _FakeAsyncClient)

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(s2_module.asyncio, "sleep", no_sleep)

    refs = await get_paper_references("10.3389/fpsyg.2022.651547")

    assert refs is None
    assert _FakeAsyncClient.call_count == 3
