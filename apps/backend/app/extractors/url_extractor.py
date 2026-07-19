"""URL metadata extractor.

Tries, in order:
1. Crossref (DOIs and dx.doi.org URLs) — structured metadata + citations count
2. HTML scraping — og:title, og:description, author, publish date
3. JSON-LD structured data (schema.org) — richer metadata from embedded scripts
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
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
    # Suggestions de taxonomie ADR-020 (LLM uniquement — les heuristiques
    # Crossref/HTML ne classifient pas). Valeurs des enums schemas.source.
    format: str | None = None
    category: str | None = None
    author_kind: str | None = None
    # Texte brut de la page, conservé pour éviter un second fetch au stage LLM.
    # Jamais sérialisé vers l'API.
    page_text: str | None = None


# ── Title cleaning ──────────────────────────────────────────────────────

# Séparateurs typiques "Titre | Site" : pipe (espaces optionnels), tirets
# moyens/longs, puces — le tiret simple exige des espaces autour pour ne pas
# couper les mots composés ("Spider-Man").
_TITLE_SEP = r"(?:\s*\|\s*|\s+[–—·•]\s+|\s+-\s+)"


def _normalize_for_match(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _site_name_candidates(site_name: str | None, url: str) -> set[str]:
    candidates: set[str] = set()
    if site_name:
        candidates.add(_normalize_for_match(site_name))
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host:
        candidates.add(_normalize_for_match(host))
        first_label = host.split(".")[0]
        candidates.add(_normalize_for_match(first_label))
    return {c for c in candidates if len(c) >= 3}


def _segment_matches_site(segment: str, candidates: set[str]) -> bool:
    seg = _normalize_for_match(segment)
    if len(seg) < 3:
        return False
    # "frontiers" matche "frontiersin" (og:site_name vs domaine et vice versa)
    return any(seg == c or seg in c or c in seg for c in candidates)


def clean_title(title: str, site_name: str | None, url: str) -> str:
    """Strip a leading/trailing site-name segment from a scraped title.

    Guard against over-cleaning: a segment is only removed when it matches
    ``og:site_name`` or the URL's hostname — a legitimate "|" or "-" inside
    the actual title is preserved.
    """
    candidates = _site_name_candidates(site_name, url)
    if not candidates:
        return title
    cleaned = title.strip()
    changed = True
    while changed:
        changed = False
        m = re.match(rf"^(.+?){_TITLE_SEP}(.+)$", cleaned)
        if m and _segment_matches_site(m.group(1), candidates):
            cleaned = m.group(2).strip()
            changed = True
            continue
        m = re.match(rf"^(.+){_TITLE_SEP}(.+?)$", cleaned)
        if m and _segment_matches_site(m.group(2), candidates):
            cleaned = m.group(1).strip()
            changed = True
    return cleaned if len(cleaned) >= 8 else title


# ── JSON-LD extraction ──────────────────────────────────────────────────


def _parse_jsonld_metadata(soup: BeautifulSoup) -> ExtractedMetadata | None:
    """Parse schema.org JSON-LD from embedded <script> tags.

    Handles Article, NewsArticle, BlogPosting, ScholarlyArticle, WebPage,
    and other schema.org types that carry ``headline`` / ``name`` /
    ``author`` / ``datePublished`` / ``description`` fields.
    Returns ``None`` when no parseable JSON-LD is found.
    """
    scripts = soup.find_all("script", type="application/ld+json")
    if not scripts:
        return None

    title: str | None = None
    authors: list[str] = []
    published_at: str | None = None
    description: str | None = None

    def _extract_text(v: object) -> str | None:
        return str(v).strip() if v else None

    def _parse_name(v: object) -> str | None:
        """Extract a human-readable name from a JSON-LD author/value."""
        if isinstance(v, dict):
            name = v.get("name")
            if isinstance(name, str):
                return name.strip()
            return None
        if isinstance(v, str):
            return v.strip()
        return None

    def _parse_author(item: object) -> list[str]:
        """Extract author names from JSON-LD author fields."""
        names: list[str] = []
        if isinstance(item, list):
            for el in item:
                n = _parse_name(el)
                if n:
                    names.append(n)
        else:
            n = _parse_name(item)
            if n:
                names.append(n)
        return names

    def _parse_date(raw: object) -> str | None:
        """Extract ISO date (at minimum ``YYYY-MM-DD``) from a date string."""
        s = _extract_text(raw)
        if not s:
            return None
        # Try full ISO datetime first
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
        # Then plain date
        try:
            return date.fromisoformat(s).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        return None

    def _extract_jsonld_data(raw: str) -> list[dict]:
        """Try to parse raw script text as one or more JSON-LD objects."""
        # Try full text first
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: try line-by-line for pages that inline multiple
            # JSON-LD objects separated by newlines in a single script tag
            results: list[dict] = []
            for line in raw.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    results.append(item)
                elif isinstance(item, list):
                    results.extend(item)
            return results

        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        return []

    for script in scripts:
        raw = script.get_text(strip=True)
        if not raw:
            continue
        blocks = _extract_jsonld_data(raw)

        for data in blocks:
            # Normalize to graph items
            graph: list[dict] = []
            if isinstance(data, dict):
                g = data.get("@graph")
                if isinstance(g, list):
                    graph.extend(g)
                else:
                    graph.append(data)

            for item in graph:
                if not isinstance(item, dict):
                    continue
                type_ = item.get("@type")
                if isinstance(type_, list):
                    type_ = type_[0] if type_ else None
                if not isinstance(type_, str):
                    continue
                # Only process types likely to carry bibliographic metadata
                if type_ in (
                    "Article",
                    "NewsArticle",
                    "BlogPosting",
                    "ScholarlyArticle",
                    "TechArticle",
                    "Report",
                    "Book",
                    "WebPage",
                    "VideoObject",
                    "AudioObject",
                    "PodcastEpisode",
                ):
                    # Title: headline > name > alternativeHeadline
                    h = _extract_text(item.get("headline"))
                    if h:
                        title = title or h
                    n = _extract_text(item.get("name"))
                    if n:
                        title = title or n

                    # Author(s)
                    author_data = item.get("author")
                    if author_data:
                        names = _parse_author(author_data)
                        for nm in names:
                            if nm not in authors:
                                authors.append(nm)

                    # Date
                    d = _parse_date(
                        item.get("datePublished")
                        or item.get("dateModified")
                        or item.get("dateCreated")
                    )
                    if d:
                        published_at = published_at or d

                    # Description
                    desc = _extract_text(item.get("description") or item.get("abstract"))
                    if desc:
                        description = description or desc

    if not any([title, authors, published_at, description]):
        return None

    return ExtractedMetadata(
        title=title,
        authors=", ".join(authors) if authors else None,
        published_at=published_at,
        description=description,
    )


# ── DOI extraction ──────────────────────────────────────────────────────


def _extract_doi(url: str) -> str | None:
    """Return bare DOI from a URL like https://doi.org/10.xxx/yyy or https://dx.doi.org/..."""
    patterns = [
        r"(?:https?://)?(?:dx\.)?doi\.org/([^\s?#]+)",
        r"doi:\s*([^\s?#]+)",
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

        # Supplement with JSON-LD structured data (richer, same HTTP response)
        jsonld_meta = _parse_jsonld_metadata(soup)
        if jsonld_meta:
            title = title or jsonld_meta.title
            description = description or jsonld_meta.description
            published_at = published_at or jsonld_meta.published_at
            if authors_raw is None and jsonld_meta.authors:
                authors_raw = jsonld_meta.authors

        if title:
            title = clean_title(title, _meta("og:site_name"), url)

        return ExtractedMetadata(
            title=title or None,
            authors=authors_raw or None,
            published_at=published_at,
            description=description or None,
            page_text=soup.get_text(separator=" ", strip=True) or None,
        )
    except Exception as e:
        logger.debug("HTML scrape failed for url=%s: %s", url, e)
        return None


async def extract(url: str) -> ExtractedMetadata:
    """Return best-effort metadata for any URL. Never raises.

    Stages: 1. Crossref (DOI) → 2. HTML/JSON-LD scrape → 3. LLM (si le proxy
    LiteLLM est configuré) qui complète les champs manquants et suggère la
    taxonomie format/category/author_kind. Les stages 1-2 restent la source
    de vérité : le LLM ne remplace jamais une valeur déjà trouvée.
    """
    # Import local : évite un cycle app.services ↔ app.extractors.
    from app.services import llm

    result = ExtractedMetadata()

    doi = _extract_doi(url)
    if doi:
        crossref_meta = await _crossref(doi)
        if crossref_meta:
            result = crossref_meta
            result.format = "texte"
            result.category = "article-scientifique"
            result.author_kind = "chercheur"

    page_text: str | None = None
    if result.title is None or result.authors is None:
        html_meta = await _html_scrape(url)
        if html_meta:
            result.title = result.title or html_meta.title
            result.authors = result.authors or html_meta.authors
            result.published_at = result.published_at or html_meta.published_at
            result.description = result.description or html_meta.description
            page_text = html_meta.page_text

    if page_text:
        llm_meta = await llm.extract_metadata(page_text, url)
        if llm_meta:
            if result.title is None and llm_meta.title:
                result.title = clean_title(llm_meta.title, None, url)
            result.authors = result.authors or llm_meta.authors
            result.published_at = result.published_at or llm_meta.published_at
            result.description = result.description or llm_meta.description
            result.format = llm_meta.format.value if llm_meta.format else None
            result.category = llm_meta.category.value if llm_meta.category else None
            result.author_kind = llm_meta.author_kind.value if llm_meta.author_kind else None

    result.page_text = None
    return result
