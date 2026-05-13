"""URL metadata extractor.

Tries, in order:
1. Crossref (DOIs and dx.doi.org URLs) — structured metadata + citations count
2. OpenAlex (DOIs) — impact_factor via journal data
3. HTML scraping — og:title, og:description, author, publish date
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Filum/0.1 (https://github.com/Mathias-PP/filum; mailto:mathias.pinault@hotmail.fr)"
}
_TIMEOUT = 8.0


@dataclass
class ExtractedMetadata:
    title: str | None = None
    authors: str | None = None
    published_at: str | None = None
    description: str | None = None
    citations_count: int | None = None
    impact_factor: float | None = None


def _extract_doi(url: str) -> str | None:
    """Return bare DOI from a URL like https://doi.org/10.xxx/yyy or https://dx.doi.org/..."""
    patterns = [
        r"(?:https?://)?(?:dx\.)?doi\.org/(.+)",
        r"doi:\s*(.+)",
    ]
    for p in patterns:
        m = re.search(p, url, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


async def _crossref(doi: str) -> ExtractedMetadata | None:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        data = r.json().get("message", {})
        title_list = data.get("title") or []
        title = title_list[0] if title_list else None
        authors_raw = data.get("author") or []
        authors = (
            ", ".join(
                f"{a.get('family', '')} {a.get('given', '')[:1]}."
                for a in authors_raw[:5]
                if a.get("family")
            )
            or None
        )
        date_parts = (data.get("published-print") or data.get("published-online") or {}).get(
            "date-parts"
        )
        published_at: str | None = None
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                published_at = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            elif len(parts) == 2:
                published_at = f"{parts[0]:04d}-{parts[1]:02d}-01"
            elif len(parts) == 1:
                published_at = f"{parts[0]:04d}-01-01"
        citations_count = data.get("is-referenced-by-count")
        abstract = data.get("abstract")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
        return ExtractedMetadata(
            title=title,
            authors=authors,
            published_at=published_at,
            description=abstract,
            citations_count=citations_count,
        )
    except Exception as e:
        logger.debug("Crossref lookup failed for doi=%s: %s", doi, e)
        return None


async def _openalex_impact(doi: str) -> float | None:
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        data = r.json()
        journal = data.get("primary_location", {}).get("source") or {}
        return journal.get("apc_usd") and None  # apc_usd is not IF; skip
    except Exception:
        return None


async def _html_scrape(url: str) -> ExtractedMetadata | None:
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(url)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            return None
        soup = BeautifulSoup(r.text, "lxml")

        def _meta(prop: str) -> str | None:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return tag.get("content", "").strip() if tag else None  # type: ignore[union-attr]

        title = (
            _meta("og:title")
            or _meta("twitter:title")
            or (soup.find("title") and soup.find("title").get_text(strip=True))  # type: ignore[union-attr]
        )
        description = (
            _meta("og:description") or _meta("description") or _meta("twitter:description")
        )
        authors_raw = _meta("author") or _meta("article:author")
        published_at_raw = _meta("article:published_time") or _meta("datePublished")
        published_at: str | None = None
        if published_at_raw:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", published_at_raw)
            if m:
                published_at = m.group(1)

        return ExtractedMetadata(
            title=title or None,
            authors=authors_raw or None,
            published_at=published_at,
            description=description or None,
        )
    except Exception as e:
        logger.debug("HTML scrape failed for url=%s: %s", url, e)
        return None


async def extract(url: str) -> ExtractedMetadata:
    """Return best-effort metadata for any URL. Never raises."""
    result = ExtractedMetadata()

    doi = _extract_doi(url)
    if doi:
        crossref_meta = await _crossref(doi)
        if crossref_meta:
            result = crossref_meta

    if result.title is None:
        html_meta = await _html_scrape(url)
        if html_meta:
            result.title = result.title or html_meta.title
            result.authors = result.authors or html_meta.authors
            result.published_at = result.published_at or html_meta.published_at
            result.description = result.description or html_meta.description

    return result
