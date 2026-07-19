"""Tests for app.extractors.url_extractor.

The extractor was added in iteration 3 PR2 without tests. It is called from
GET /api/v1/sources/extract which is reachable without authentication, so
correctness and silent-failure are both important.

Tests cover:
- DOI parsing (regex-only, no I/O)
- The two paths of extract(): Crossref hit and HTML scrape fallback
- Silent failure on network errors (extract() must NEVER raise)
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.extractors.url_extractor import (
    ExtractedMetadata,
    _extract_doi,
    _extract_pii,
    _parse_jsonld_metadata,
    clean_title,
    extract,
)


class TestCleanTitle:
    def test_strips_leading_site_name_pipe(self):
        assert (
            clean_title(
                "Frontiers | Cognitive reserve and aging",
                None,
                "https://www.frontiersin.org/articles/10.3389/fnagi.2024.1234",
            )
            == "Cognitive reserve and aging"
        )

    def test_strips_trailing_site_name_dash(self):
        assert (
            clean_title(
                "Understanding memory consolidation - Nature",
                "Nature",
                "https://www.nature.com/articles/xyz",
            )
            == "Understanding memory consolidation"
        )

    def test_strips_via_og_site_name_when_domain_differs(self):
        assert (
            clean_title(
                "Le Monde | La mémoire des lieux",
                "Le Monde",
                "https://lemonde.fr/sciences/article",
            )
            == "La mémoire des lieux"
        )

    def test_keeps_legitimate_pipe_in_title(self):
        title = "Pipes | A history of plumbing"
        assert clean_title(title, "Example Blog", "https://example.com/post") == title

    def test_keeps_hyphenated_words(self):
        title = "Spider-Man et la cognition"
        assert clean_title(title, "Frontiers", "https://frontiersin.org/x") == title

    def test_keeps_dash_segment_not_matching_site(self):
        title = "La mémoire - une exploration"
        assert clean_title(title, "Nature", "https://nature.com/articles/x") == title

    def test_no_over_cleaning_when_remainder_too_short(self):
        # Si le nettoyage laisse un résidu trop court, on garde l'original.
        title = "Nature - Vol. 3"
        assert clean_title(title, "Nature", "https://nature.com/x") == title

    def test_strips_both_ends(self):
        assert (
            clean_title(
                "Frontiers | Cognitive reserve and aging | Frontiers",
                "Frontiers",
                "https://frontiersin.org/articles/x",
            )
            == "Cognitive reserve and aging"
        )


class TestExtractDoi:
    def test_canonical_doi_org_url(self):
        assert _extract_doi("https://doi.org/10.1038/s41586-023-06501-x") == (
            "10.1038/s41586-023-06501-x"
        )

    def test_dx_doi_org_url(self):
        assert _extract_doi("https://dx.doi.org/10.1234/abcd") == "10.1234/abcd"

    def test_doi_prefix_in_text(self):
        assert _extract_doi("doi: 10.1038/foo.bar") == "10.1038/foo.bar"

    def test_no_doi_returns_none(self):
        assert _extract_doi("https://www.nature.com/articles/xyz") is None

    def test_strips_query_and_fragment(self):
        assert _extract_doi("https://doi.org/10.1/x?ref=y#sec") == "10.1/x"

    def test_publisher_path_doi_springer(self):
        assert _extract_doi("https://link.springer.com/article/10.1007/s11229-020-02724-x") == (
            "10.1007/s11229-020-02724-x"
        )

    def test_publisher_path_doi_wiley_full(self):
        assert _extract_doi("https://onlinelibrary.wiley.com/doi/full/10.1002/hipo.22488") == (
            "10.1002/hipo.22488"
        )

    def test_publisher_path_doi_strips_trailing_segment(self):
        assert _extract_doi(
            "https://onlinelibrary.wiley.com/doi/10.1111/j.1467-8624.2010.01564.x/abstract"
        ) == ("10.1111/j.1467-8624.2010.01564.x")


class TestExtractPii:
    def test_sciencedirect_abs_url(self):
        assert (
            _extract_pii("https://www.sciencedirect.com/science/article/abs/pii/S0165032717310960")
            == "S0165032717310960"
        )

    def test_linkinghub_elsevier(self):
        assert (
            _extract_pii("https://linkinghub.elsevier.com/retrieve/pii/S0165032717310960")
            == "S0165032717310960"
        )

    def test_check_digit_x(self):
        assert (
            _extract_pii("https://www.sciencedirect.com/science/article/pii/S089662730800123X")
            == "S089662730800123X"
        )

    def test_non_elsevier_host_returns_none(self):
        assert _extract_pii("https://example.com/pii/S0165032717310960") is None


# ---------------------------------------------------------------------------
# JSON-LD extraction (no I/O, pure parsing)
# ---------------------------------------------------------------------------


def _soup(html: str) -> Any:
    """Shortcut to get a BeautifulSoup from a string."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml")


JSONLD_ARTICLE_FIXTURE = """<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "The Memory Article",
  "author": [
    {"@type": "Person", "name": "Stanislas Dehaene"},
    {"@type": "Person", "name": "Howard Eichenbaum"}
  ],
  "datePublished": "2024-08-15T10:00:00Z",
  "description": "A compelling study about memory consolidation."
}
</script>
</head><body></body></html>"""


class TestJsonLdExtraction:
    def test_article_with_full_metadata(self):
        meta = _parse_jsonld_metadata(_soup(JSONLD_ARTICLE_FIXTURE))
        assert meta is not None
        assert meta.title == "The Memory Article"
        assert meta.authors == "Stanislas Dehaene, Howard Eichenbaum"
        assert meta.published_at == "2024-08-15"
        assert meta.description == "A compelling study about memory consolidation."

    def test_returns_none_when_no_jsonld(self):
        html = "<html><head></head><body></body></html>"
        meta = _parse_jsonld_metadata(_soup(html))
        assert meta is None

    def test_single_author_string(self):
        html = """<html><head>
<script type="application/ld+json">
{"@type":"Article","author":{"@type":"Person","name":"Jane Doe"},"headline":"Title"}
</script>
</head></html>"""
        meta = _parse_jsonld_metadata(_soup(html))
        assert meta is not None
        assert meta.authors == "Jane Doe"

    def test_ignores_non_bibliographic_types(self):
        html = """<html><head>
<script type="application/ld+json">
{"@type":"BreadcrumbList","itemListElement":[]}
</script>
</head></html>"""
        meta = _parse_jsonld_metadata(_soup(html))
        assert meta is None

    def test_uses_name_when_headline_missing(self):
        html = """<html><head>
<script type="application/ld+json">
{"@type":"WebPage","name":"Page Name","description":"Desc"}
</script>
</head></html>"""
        meta = _parse_jsonld_metadata(_soup(html))
        assert meta is not None
        assert meta.title == "Page Name"

    def test_date_variants(self):
        """ISO datetime, plain date, and embedded prefix patterns."""
        cases = [
            ("2024-03-15T14:30:00Z", "2024-03-15"),
            ("2024-03-15", "2024-03-15"),
        ]
        for raw, expected in cases:
            html = f"""<html><head>
<script type="application/ld+json">
{{"@type":"Article","headline":"T","datePublished":"{raw}"}}
</script>
</head></html>"""
            meta = _parse_jsonld_metadata(_soup(html))
            assert meta is not None and meta.published_at == expected, f"Failed for {raw}"

    def test_multiple_script_tags(self):
        """Multiple JSON-LD blocks: merge metadata from relevant ones."""
        html = """<html><head>
<script type="application/ld+json">
{"@type":"WebPage","name":"Page Name"}
</script>
<script type="application/ld+json">
{"@type":"Article","headline":"Article Title","author":{"@type":"Person","name":"Author"}}
</script>
</head></html>"""
        meta = _parse_jsonld_metadata(_soup(html))
        assert meta is not None
        assert meta.title == "Page Name"  # first valid title wins
        assert meta.authors == "Author"


# ---------------------------------------------------------------------------
# JSON-LD supplement in full HTML scrape (no extra I/O)
# ---------------------------------------------------------------------------


JSONLD_AND_OG_FIXTURE = """<!DOCTYPE html>
<html>
  <head>
    <meta property="og:title" content="OG Title">
    <meta name="description" content="OG Description">
    <script type="application/ld+json">
    {"@type":"Article","author":{"@type":"Person","name":"JSON-LD Author"},"datePublished":"2025-01-01"}
    </script>
  </head>
  <body></body>
</html>"""


@pytest.mark.asyncio
async def test_extract_html_with_jsonld_supplement(monkeypatch):
    """JSON-LD fills fields missing from OG tags (e.g. author if no meta author)."""
    fake = _FakeAsyncClient(
        response=_FakeResponse(
            200,
            text=JSONLD_AND_OG_FIXTURE,
            headers={"content-type": "text/html"},
        )
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/jsonld-article")

    assert result.title == "OG Title"  # OG wins
    assert result.description == "OG Description"  # OG wins
    assert result.authors == "JSON-LD Author"  # from JSON-LD (no meta author)
    assert result.published_at == "2025-01-01"  # from JSON-LD (no meta date)


# ---------------------------------------------------------------------------
# Helpers to mock httpx.AsyncClient without pulling in respx/pytest-httpx
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(
        self, status_code: int, json_body: Any = None, text: str = "", headers: dict | None = None
    ):
        self.status_code = status_code
        self._json = json_body
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        return self._json


class _FakeAsyncClient:
    """Drop-in replacement for httpx.AsyncClient supporting `async with` + .get."""

    def __init__(
        self,
        *,
        response: _FakeResponse | None = None,
        raise_exc: Exception | None = None,
        **_kwargs,
    ):
        self._response = response
        self._raise = raise_exc
        self.last_url: str | None = None

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        self.last_url = url
        if self._raise is not None:
            raise self._raise
        assert self._response is not None
        return self._response


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, fake: _FakeAsyncClient) -> None:
    monkeypatch.setattr(
        "app.extractors.url_extractor.httpx.AsyncClient",
        lambda *a, **kw: fake,
    )


# ---------------------------------------------------------------------------
# extract() — Crossref happy path
# ---------------------------------------------------------------------------


CROSSREF_OK_PAYLOAD = {
    "message": {
        "title": ["A study about memory"],
        "author": [
            {"family": "Dehaene", "given": "Stanislas"},
            {"family": "Eichenbaum", "given": "Howard"},
        ],
        "published-print": {"date-parts": [[2024, 3, 15]]},
        "is-referenced-by-count": 42,
        "abstract": "<jats:p>Some <i>abstract</i>.</jats:p>",
    }
}


@pytest.mark.asyncio
async def test_extract_doi_returns_crossref_metadata(monkeypatch):
    fake = _FakeAsyncClient(response=_FakeResponse(200, json_body=CROSSREF_OK_PAYLOAD))
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://doi.org/10.1038/s41586-024-12345-x")

    assert isinstance(result, ExtractedMetadata)
    assert result.title == "A study about memory"
    assert "Dehaene" in (result.authors or "")
    assert result.published_at == "2024-03-15"
    assert result.citations_count == 42
    # JATS-style XML tags must be stripped from the abstract
    assert result.description is not None
    assert "<" not in result.description and ">" not in result.description


CROSSREF_PII_PAYLOAD = {
    "message": {
        "items": [
            {
                "title": ["Cognitive bias modification: A review of meta-analyses"],
                "author": [
                    {"family": "Jones", "given": "Emma B."},
                    {"family": "Sharpe", "given": "Louise"},
                ],
                "published-print": {"date-parts": [[2017, 12]]},
                "is-referenced-by-count": 200,
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_extract_sciencedirect_pii_via_crossref(monkeypatch):
    """URL ScienceDirect sans DOI : le PII doit être résolu via Crossref."""
    fake = _FakeAsyncClient(response=_FakeResponse(200, json_body=CROSSREF_PII_PAYLOAD))
    _patch_async_client(monkeypatch, fake)

    result = await extract(
        "https://www.sciencedirect.com/science/article/abs/pii/S0165032717310960"
    )

    assert fake.last_url is not None
    assert "alternative-id:S0165032717310960" in fake.last_url
    assert result.title == "Cognitive bias modification: A review of meta-analyses"
    assert "Jones" in (result.authors or "")
    assert result.published_at == "2017-12-01"
    assert result.category == "article-scientifique"


# ---------------------------------------------------------------------------
# extract() — HTML scrape fallback
# ---------------------------------------------------------------------------


HTML_FIXTURE = """<!DOCTYPE html>
<html>
  <head>
    <meta property="og:title" content="OG Title">
    <meta property="og:description" content="OG Description">
    <meta name="author" content="Doe, J.">
    <meta property="article:published_time" content="2023-06-01T12:00:00Z">
  </head>
  <body>content</body>
</html>"""


@pytest.mark.asyncio
async def test_extract_non_doi_falls_back_to_html(monkeypatch):
    fake = _FakeAsyncClient(
        response=_FakeResponse(
            200,
            text=HTML_FIXTURE,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/article")

    assert result.title == "OG Title"
    assert result.description == "OG Description"
    assert result.authors == "Doe, J."
    assert result.published_at == "2023-06-01"


@pytest.mark.asyncio
async def test_extract_returns_empty_when_html_is_not_html(monkeypatch):
    fake = _FakeAsyncClient(
        response=_FakeResponse(
            200, text="binary", headers={"content-type": "application/octet-stream"}
        )
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/file.bin")

    # No DOI, HTML rejected → empty metadata, but no exception.
    assert result.title is None
    assert result.authors is None


# ---------------------------------------------------------------------------
# extract() — silent failure contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_swallows_network_errors(monkeypatch):
    """extract() must NEVER raise, even on connection failure."""
    fake = _FakeAsyncClient(raise_exc=httpx.ConnectError("nope"))
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://unreachable.invalid/")

    assert isinstance(result, ExtractedMetadata)
    assert result.title is None


@pytest.mark.asyncio
async def test_extract_swallows_non_200(monkeypatch):
    fake = _FakeAsyncClient(response=_FakeResponse(503, text=""))
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://doi.org/10.999/does-not-exist")

    # Crossref 503 → no DOI metadata. HTML scrape will also 503 → empty.
    assert result.title is None
