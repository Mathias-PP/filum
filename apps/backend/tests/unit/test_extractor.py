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

from app.extractors import url_extractor
from app.extractors.url_extractor import (
    ExtractedMetadata,
    _extract_doi,
    _extract_pii,
    _extract_pubmed_id,
    _looks_like_challenge_page,
    _parse_jsonld_metadata,
    clean_title,
    doi_from_page_meta,
    extract,
    resolve_doi_from_pubmed,
    resolve_doi_from_url,
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

    def test_url_without_doi_is_not_guessed(self):
        """Aucune deduction par editeur : une URL qui ne porte pas son DOI rend
        None ici, c'est `resolve_doi_from_url` qui interroge les index. Deviner
        le DOI depuis le slug ne marcherait que pour les editeurs codes en dur."""
        assert _extract_doi("https://www.nature.com/articles/nrn3667") is None
        assert _extract_doi("https://www.nature.com/articles/xyz") is None

    def test_biorxiv_url_strips_version_suffix(self):
        """bioRxiv publie un DOI par version (`...v1`, `...v2.full`) mais
        Crossref n'indexe que la forme canonique sans version."""
        assert (
            _extract_doi("https://www.biorxiv.org/content/10.1101/2024.01.15.575984v1")
            == "10.1101/2024.01.15.575984"
        )
        assert (
            _extract_doi("https://www.biorxiv.org/content/10.1101/2024.01.15.575984v2.full")
            == "10.1101/2024.01.15.575984"
        )

    def test_medrxiv_url_strips_version_suffix(self):
        assert (
            _extract_doi("https://www.medrxiv.org/content/10.1101/2023.05.10.12345v1")
            == "10.1101/2023.05.10.12345"
        )


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

    async def get(self, url: str, **_kwargs) -> _FakeResponse:
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


# ---------------------------------------------------------------------------
# Pages-obstacle anti-bot (Cloudflare, reCAPTCHA, DataDome…)
# ---------------------------------------------------------------------------


class TestChallengePageDetection:
    def test_recaptcha_title_is_a_challenge(self):
        assert _looks_like_challenge_page("Checking your browser - reCAPTCHA", "") is True

    def test_cloudflare_interstitial_is_a_challenge(self):
        assert _looks_like_challenge_page("Just a moment...", "") is True

    def test_short_body_signature_is_a_challenge(self):
        assert _looks_like_challenge_page("", "Please verify you are human to continue.") is True

    def test_legitimate_article_about_captchas_is_not_a_challenge(self):
        """Un vrai article qui *parle* de CAPTCHA ne doit pas être rejeté."""
        body = "How reCAPTCHA works under the hood. " * 100
        assert _looks_like_challenge_page("How reCAPTCHA works under the hood", body) is False

    def test_ordinary_page_is_not_a_challenge(self):
        assert _looks_like_challenge_page("A study about memory", "Some article body.") is False

    def test_radware_client_challenge_is_a_challenge(self):
        """Le titre servi par nature.com derriere Radware, vu en prod le 2026-08-04."""
        assert _looks_like_challenge_page("Client Challenge", "") is True

    def test_imperva_challenge_validation_is_a_challenge(self):
        assert _looks_like_challenge_page("Challenge Validation", "") is True

    def test_provider_name_on_empty_page_is_a_challenge(self):
        assert _looks_like_challenge_page("Attention", "Enable JavaScript to continue") is True

    def test_generic_word_on_a_real_article_is_not_a_challenge(self):
        """« challenge » est un mot ordinaire : il ne suffit pas sur une vraie page."""
        body = "The challenge of reproducibility in psychology. " * 30
        assert _looks_like_challenge_page("The challenge of reproducibility", body) is False

    def test_short_legitimate_page_mentioning_challenge_is_not_a_challenge(self):
        """Une page breve mais reelle (>200 car.) garde le benefice du doute."""
        body = "This challenge was set by the lab in 2019 to test memory recall. " * 5
        assert _looks_like_challenge_page("A memory challenge", body) is False


@pytest.mark.asyncio
async def test_extract_discards_challenge_page_metadata(monkeypatch):
    """Le titre d'une page-obstacle ne doit jamais remonter dans le formulaire."""
    challenge_html = (
        "<html><head><title>Checking your browser - reCAPTCHA</title></head>"
        "<body>Please enable JavaScript and cookies to continue.</body></html>"
    )
    fake = _FakeAsyncClient(
        response=_FakeResponse(
            200, text=challenge_html, headers={"content-type": "text/html; charset=utf-8"}
        )
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/blocked")

    assert result.title is None
    assert result.description is None
    assert result.access_blocked is True


@pytest.mark.asyncio
async def test_extract_reports_http_refusal_as_blocked(monkeypatch):
    """403 : le site a compris et refuse. Ce n'est pas « page introuvable »."""
    fake = _FakeAsyncClient(response=_FakeResponse(403, text="Forbidden", headers={}))
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/paywalled")

    assert result.title is None
    assert result.access_blocked is True


@pytest.mark.asyncio
async def test_extract_does_not_report_blocked_when_page_reads_fine(monkeypatch):
    html = "<html><head><title>A real article</title></head><body>%s</body></html>" % (
        "Real content. " * 200
    )
    fake = _FakeAsyncClient(
        response=_FakeResponse(200, text=html, headers={"content-type": "text/html"})
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://example.com/article")

    assert result.access_blocked is False


# ---------------------------------------------------------------------------
# Oracle PubMed/PMC : PMID → DOI → Crossref
# ---------------------------------------------------------------------------


class TestExtractPubmedId:
    def test_pmid_from_pubmed_url(self):
        assert _extract_pubmed_id("https://pubmed.ncbi.nlm.nih.gov/36300046/") == "36300046"

    def test_pmid_without_trailing_slash(self):
        assert _extract_pubmed_id("https://pubmed.ncbi.nlm.nih.gov/36300046") == "36300046"

    def test_pmcid_from_pmc_url(self):
        assert (
            _extract_pubmed_id("https://pmc.ncbi.nlm.nih.gov/articles/PMC9588931/") == "PMC9588931"
        )

    def test_non_pubmed_url_returns_none(self):
        assert _extract_pubmed_id("https://example.com/36300046/") is None


class _SequencedAsyncClient(_FakeAsyncClient):
    """Renvoie une réponse différente par appel, dans l'ordre fourni."""

    def __init__(self, responses: list[_FakeResponse], **_kwargs):
        super().__init__()
        self._responses = responses
        self.urls: list[str] = []

    async def get(self, url: str, **_kwargs) -> _FakeResponse:
        self.urls.append(url)
        return self._responses[min(len(self.urls) - 1, len(self._responses) - 1)]


IDCONV_OK_PAYLOAD = {
    "status": "ok",
    "records": [
        {"doi": "10.3389/fpsyg.2022.651547", "pmcid": "PMC9588931", "pmid": 36300046},
    ],
}


@pytest.mark.asyncio
async def test_extract_pubmed_url_resolves_doi_then_crossref(monkeypatch):
    fake = _SequencedAsyncClient(
        [
            _FakeResponse(200, json_body=IDCONV_OK_PAYLOAD),
            _FakeResponse(200, json_body=CROSSREF_OK_PAYLOAD),
        ]
    )
    _patch_async_client(monkeypatch, fake)

    result = await extract("https://pubmed.ncbi.nlm.nih.gov/36300046/")

    assert "ids=36300046" in fake.urls[0]
    assert "10.3389/fpsyg.2022.651547" in fake.urls[1]
    assert result.title == "A study about memory"
    assert result.category == "article-scientifique"


@pytest.mark.asyncio
async def test_resolve_doi_from_pubmed_returns_none_on_error(monkeypatch):
    fake = _FakeAsyncClient(raise_exc=httpx.ConnectError("nope"))
    _patch_async_client(monkeypatch, fake)

    assert await resolve_doi_from_pubmed("https://pubmed.ncbi.nlm.nih.gov/36300046/") is None


# ---------------------------------------------------------------------------
# resolve_doi_from_url — resolution generique, sans connaissance de l'editeur
# ---------------------------------------------------------------------------


S2_URL_OK_PAYLOAD = {"paperId": "abc", "externalIds": {"DOI": "10.1038/NRN3667"}}
_HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}

# Extrait reel du <head> de https://www.nature.com/articles/nrn3667.
NATURE_HEAD = """<html><head>
<meta name="prism.doi" content="doi:10.1038/nrn3667"/>
<meta name="dc.identifier" content="doi:10.1038/nrn3667"/>
<meta name="citation_doi" content="10.1038/nrn3667"/>
</head><body></body></html>"""


@pytest.fixture(autouse=True)
def _clear_url_doi_cache():
    url_extractor._url_doi_cache.clear()
    yield
    url_extractor._url_doi_cache.clear()


class TestDoiFromPageMeta:
    def test_highwire_citation_doi(self):
        assert doi_from_page_meta(NATURE_HEAD) == "10.1038/nrn3667"

    def test_prism_doi_prefix_is_stripped(self):
        html = '<meta name="prism.doi" content="doi:10.1038/nrn3667">'
        assert doi_from_page_meta(html) == "10.1038/nrn3667"

    def test_meta_name_is_case_insensitive(self):
        html = '<meta name="CITATION_DOI" content="10.1371/journal.pone.0123456">'
        assert doi_from_page_meta(html) == "10.1371/journal.pone.0123456"

    def test_dc_identifier_holding_an_issn_is_ignored(self):
        """`dc.identifier` sert aussi aux ISSN/ISBN : seul un DOI est retenu."""
        assert doi_from_page_meta('<meta name="dc.identifier" content="1471-003X">') is None

    def test_page_without_doi_meta(self):
        assert doi_from_page_meta("<html><head><title>Un blog</title></head></html>") is None


@pytest.mark.asyncio
async def test_resolve_doi_from_url_reads_publisher_meta(monkeypatch):
    """Nature ne met pas le DOI dans l'URL mais le declare dans sa page."""
    fake = _FakeAsyncClient(response=_FakeResponse(200, text=NATURE_HEAD, headers=_HTML_HEADERS))
    _patch_async_client(monkeypatch, fake)

    doi = await resolve_doi_from_url("https://www.nature.com/articles/nrn3667")

    assert doi == "10.1038/nrn3667"
    assert fake.last_url == "https://www.nature.com/articles/nrn3667"


@pytest.mark.asyncio
async def test_resolve_doi_from_url_falls_back_to_semantic_scholar(monkeypatch):
    """Page refusee (403) : S2 sait parfois relier l'URL a un papier."""
    fake = _SequencedAsyncClient(
        [
            _FakeResponse(403, text=""),
            _FakeResponse(200, json_body=S2_URL_OK_PAYLOAD),
        ]
    )
    _patch_async_client(monkeypatch, fake)

    doi = await resolve_doi_from_url("https://www.nature.com/articles/nrn3667")

    assert doi == "10.1038/nrn3667"
    assert "semanticscholar.org" in fake.urls[1]


@pytest.mark.asyncio
async def test_resolve_doi_from_url_returns_none_when_unknown(monkeypatch):
    """Une URL sans identite bibliographique (blog, video) ne rend rien."""
    fake = _SequencedAsyncClient(
        [
            _FakeResponse(200, text="<html><head></head></html>", headers=_HTML_HEADERS),
            _FakeResponse(404, json_body={"error": "not found"}),
        ]
    )
    _patch_async_client(monkeypatch, fake)

    assert await resolve_doi_from_url("https://exemple.fr/mon-billet") is None


@pytest.mark.asyncio
async def test_resolve_doi_from_url_survives_network_error(monkeypatch):
    fake = _FakeAsyncClient(raise_exc=httpx.ConnectError("nope"))
    _patch_async_client(monkeypatch, fake)

    assert await resolve_doi_from_url("https://www.nature.com/articles/nrn3667") is None


@pytest.mark.asyncio
async def test_resolve_doi_from_url_caches_result(monkeypatch):
    """Le meme import resout l'URL plusieurs fois : une seule requete reseau."""
    fake = _SequencedAsyncClient([_FakeResponse(200, text=NATURE_HEAD, headers=_HTML_HEADERS)])
    _patch_async_client(monkeypatch, fake)

    url = "https://www.nature.com/articles/nrn3667"
    assert await resolve_doi_from_url(url) == "10.1038/nrn3667"
    assert await resolve_doi_from_url(url) == "10.1038/nrn3667"
    assert len(fake.urls) == 1


class TestCrossrefPublicationDate:
    """Signale a l'usage le 2026-08-04 : la fiche stockait `published_at = null`
    pour un preprint alors que Crossref connaissait la date.

    Cause mesuree : un enregistrement `posted-content` (OSF, bioRxiv, medRxiv,
    PsyArXiv) ne porte **ni** `published-print` **ni** `published-online` — les
    deux seuls champs lus. Sa date vit dans `issued`, present lui sur tous les
    types. La donnee etait disponible et jetee.
    """

    def test_un_preprint_a_bien_une_date(self):
        # Reponse Crossref reelle pour 10.31234/osf.io/x4yj3 (Hardee et al.).
        meta = url_extractor._parse_crossref_work(
            {
                "type": "posted-content",
                "title": ["Development of inhibitory control"],
                "issued": {"date-parts": [[2021, 9, 9]]},
            }
        )
        assert meta.published_at == "2021-09-09"

    def test_la_date_de_parution_papier_reste_prioritaire(self):
        """`issued` n'est qu'un repli : il ne doit rien changer aux
        enregistrements qui declarent deja leur parution."""
        meta = url_extractor._parse_crossref_work(
            {
                "published-print": {"date-parts": [[2014, 3]]},
                "published-online": {"date-parts": [[2014, 2, 5]]},
                "issued": {"date-parts": [[2014, 2, 5]]},
            }
        )
        assert meta.published_at == "2014-03-01"

    def test_sans_aucune_date_le_champ_reste_vide(self):
        """Une date inventee serait pire que pas de date : la chronologie
        placerait l'oeuvre a une position qui affirme quelque chose de faux."""
        meta = url_extractor._parse_crossref_work({"title": ["Sans date"]})
        assert meta.published_at is None
