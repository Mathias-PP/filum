"""Tests du service LLM (parsing structured output + désactivation propre)."""

from __future__ import annotations

import json

import pytest

from app.extractors import url_extractor
from app.services import llm
from app.services.llm import LlmSourceMetadata, parse_metadata_content


class TestParseMetadataContent:
    def test_valid_full_payload(self):
        content = json.dumps(
            {
                "title": "Mémoire et cerveau",
                "authors": "Dupont A., Martin B.",
                "published_at": "2025-03-12",
                "description": "Une synthèse.",
                "format": "texte",
                "category": "article-scientifique",
                "author_kind": "chercheur",
            }
        )
        meta = parse_metadata_content(content)
        assert meta is not None
        assert meta.title == "Mémoire et cerveau"
        assert meta.category is not None and meta.category.value == "article-scientifique"

    def test_nulls_are_accepted(self):
        meta = parse_metadata_content(json.dumps({"title": None, "category": None}))
        assert meta is not None
        assert meta.title is None
        assert meta.category is None

    def test_invalid_enum_value_dropped_but_rest_kept(self):
        content = json.dumps({"title": "Titre", "category": "hors-taxonomie"})
        meta = parse_metadata_content(content)
        assert meta is not None
        assert meta.title == "Titre"
        assert meta.category is None

    def test_garbage_returns_none(self):
        assert parse_metadata_content("pas du json") is None
        assert parse_metadata_content(json.dumps(["une", "liste"])) is None


class TestExtractMetadataDisabled:
    async def test_returns_none_when_litellm_not_configured(self, monkeypatch):
        settings = llm.get_settings()
        monkeypatch.setattr(settings, "litellm_base_url", "")
        assert await llm.extract_metadata("du texte", "https://example.org") is None


class TestExtractorLlmStage:
    async def test_llm_fills_missing_fields_without_overriding(self, monkeypatch):
        async def fake_crossref(doi):
            return None

        async def fake_scrape(url):
            return url_extractor.ExtractedMetadata(
                title="Titre heuristique", page_text="corps de page"
            )

        async def fake_llm(page_text, url):
            assert page_text == "corps de page"
            return LlmSourceMetadata(
                title="Titre LLM (ne doit pas gagner)",
                authors="Doe J.",
                category="blog",
                author_kind="individu",
                format="texte",
            )

        monkeypatch.setattr(url_extractor, "_crossref", fake_crossref)
        monkeypatch.setattr(url_extractor, "_html_scrape", fake_scrape)
        monkeypatch.setattr(llm, "extract_metadata", fake_llm)

        meta = await url_extractor.extract("https://example.org/post")
        assert meta.title == "Titre heuristique"  # heuristique prioritaire
        assert meta.authors == "Doe J."  # complété par le LLM
        assert meta.category == "blog"
        assert meta.author_kind == "individu"
        assert meta.page_text is None  # jamais exposé

    async def test_doi_sets_taxonomy_without_llm(self, monkeypatch):
        async def fake_crossref(doi):
            return url_extractor.ExtractedMetadata(title="Papier", authors="Curie M.")

        llm_called = False

        async def fake_llm(page_text, url):
            nonlocal llm_called
            llm_called = True
            return None

        monkeypatch.setattr(url_extractor, "_crossref", fake_crossref)
        monkeypatch.setattr(llm, "extract_metadata", fake_llm)

        meta = await url_extractor.extract("https://doi.org/10.1000/xyz123")
        assert meta.category == "article-scientifique"
        assert meta.author_kind == "chercheur"
        assert llm_called is False  # Crossref complet → pas de scrape ni LLM

    async def test_extract_never_raises_when_llm_errors(self, monkeypatch):
        async def fake_crossref(doi):
            return None

        async def fake_scrape(url):
            return url_extractor.ExtractedMetadata(title="T", page_text="texte")

        async def fake_llm(page_text, url):
            return None  # contrat : never raises, None en cas d'échec

        monkeypatch.setattr(url_extractor, "_crossref", fake_crossref)
        monkeypatch.setattr(url_extractor, "_html_scrape", fake_scrape)
        monkeypatch.setattr(llm, "extract_metadata", fake_llm)

        meta = await url_extractor.extract("https://example.org")
        assert meta.title == "T"
        assert meta.category is None


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Garde-fou : aucun test de ce module ne doit sortir sur le réseau."""

    class _Blocked:
        def __init__(self, *a, **k):
            raise AssertionError("network access attempted in unit test")

    monkeypatch.setattr("httpx.AsyncClient", _Blocked)
