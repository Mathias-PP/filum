"""URL metadata extractor.

Tries, in order:
1. Crossref (DOIs and dx.doi.org URLs) — structured metadata + citations count
2. HTML scraping — og:title, og:description, author, publish date
3. JSON-LD structured data (schema.org) — richer metadata from embedded scripts
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.extractors.semantic_scholar import SemanticScholarRef

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
    # Suggestions de taxonomie ADR-020 (LLM uniquement — les heuristiques
    # Crossref/HTML ne classifient pas). Valeurs des enums schemas.source.
    format: str | None = None
    category: str | None = None
    author_kind: str | None = None
    # Metadonnees bibliographiques (Crossref uniquement, null sinon).
    journal: str | None = None
    volume: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    # Texte brut de la page, conservé pour éviter un second fetch au stage LLM.
    # Jamais sérialisé vers l'API.
    page_text: str | None = None
    # Le site a refusé l'accès (obstacle anti-bot, 403, 429). À distinguer d'une
    # page dont on n'a simplement rien tiré : « je n'ai pas eu le droit de lire »
    # n'est pas « il n'y avait rien à lire », et le formulaire doit le dire.
    access_blocked: bool = False


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


# Suffixes de chemin ajoutés par les éditeurs après le DOI dans leurs URLs
# (ex. Wiley /doi/full/10.1002/xxx, T&F /doi/pdf/10.1080/yyy/abstract).
_DOI_PATH_SUFFIXES = re.compile(r"/(?:full|abstract|pdf|epdf|epub|meta|figures|references)$", re.I)

# bioRxiv / medRxiv publient un DOI par version (`10.1101/YYYY.MM.DD.NNNNvN`).
# Crossref n'indexe QUE la forme canonique sans version : sans ce nettoyage,
# la resolution renvoie un 404 alors que le papier existe. Cf. bioRxiv docs.
_BIORXIV_VERSION_RE = re.compile(r"^(10\.1101/\d{4}\.\d{2}\.\d{2}\.\d+)v\d+(?:\.full)?$")


def _extract_doi(url: str) -> str | None:
    """Return bare DOI from a URL.

    Handles doi.org/dx.doi.org links, ``doi:`` prefixes et DOIs embarques dans
    le chemin d'une URL d'editeur (Wiley, Springer, PLOS, Taylor & Francis,
    PNAS, bioRxiv…). Purement syntaxique : quand l'URL ne porte pas son DOI,
    c'est `resolve_doi_from_url` qui interroge les index.
    """
    patterns = [
        r"(?:https?://)?(?:dx\.)?doi\.org/([^\s?#]+)",
        r"doi:\s*([^\s?#]+)",
        # DOI dans le chemin d'une URL d'éditeur : /doi/10.1002/…, /article/10.1007/…
        r"/(10\.\d{4,9}/[^\s?#]+)",
    ]
    for p in patterns:
        m = re.search(p, url, re.IGNORECASE)
        if m:
            doi = m.group(1).strip().rstrip(".,;)")
            doi = _DOI_PATH_SUFFIXES.sub("", doi)
            biorxiv_match = _BIORXIV_VERSION_RE.match(doi)
            if biorxiv_match:
                doi = biorxiv_match.group(1)
            return doi
    return None


# Signatures des pages-obstacle servies par les protections anti-bot
# (Cloudflare, reCAPTCHA, DataDome, Akamai, Imperva…). Elles renvoient un 200
# text/html tout à fait valide : sans ce garde, leur <title> finit dans le
# formulaire à la place du vrai titre du contenu.
# Formulations qu'aucune page de contenu n'emploie : elles suffisent seules.
_CHALLENGE_STRONG = (
    "just a moment",
    "checking your browser",
    "checking if the site connection is secure",
    "attention required",
    "verify you are human",
    "verifying you are human",
    "enable javascript and cookies to continue",
    "ddos protection by",
    "access denied",
    "request blocked",
    "unusual traffic from your computer",
    "vérification de votre navigateur",
    # Famille Radware / Akamai / Imperva : le titre est le seul contenu de la
    # page, le corps n'étant qu'un script. Aucun article ne s'intitule ainsi.
    "client challenge",
    "challenge validation",
    "incapsula incident",
    "pardon our interruption",
    "one more step",
    "additional security check",
)

# Termes qu'un article légitime peut employer en parlant du sujet. On ne les
# retient que sur une page anormalement courte, signature d'un interstitiel.
_CHALLENGE_WEAK = (
    "recaptcha",
    "captcha",
    "are you a human",
    "are you a robot",
    "bot detection",
    "human verification",
    "press and hold",
    # Noms des fournisseurs : sur une page longue c'est un sujet d'article, sur
    # une page courte c'est la bannière de l'obstacle.
    "incapsula",
    "datadome",
    "perimeterx",
)

# Mots qu'un texte ordinaire emploie couramment (« the challenge of… »). On ne
# les retient que sur une page vide de contenu, où ils ne peuvent plus être
# qu'une bannière d'obstacle.
_CHALLENGE_GENERIC = (
    "challenge",
    "security check",
    "cloudflare",
    "enable javascript",
    "javascript is disabled",
)

# En deçà, la page ne porte aucun contenu : son corps se réduit à un script.
_CHALLENGE_EMPTY_BODY = 200

# Un interstitiel tient en quelques centaines de caractères ; un article non.
_CHALLENGE_MAX_BODY = 2000


def _looks_like_challenge_page(title: str | None, page_text: str | None) -> bool:
    """True si la page récupérée est un obstacle anti-bot, pas le contenu.

    Trois niveaux d'exigence, du plus au moins tolérant sur le vocabulaire :
    une formulation qu'aucun contenu n'emploie suffit seule ; un nom de
    fournisseur exige une page courte ; un mot ordinaire exige une page vide.
    """
    haystack = f"{title or ''} {page_text or ''}".lower()
    if any(sig in haystack for sig in _CHALLENGE_STRONG):
        return True
    body_len = len(page_text or "")
    if body_len < _CHALLENGE_MAX_BODY and any(sig in haystack for sig in _CHALLENGE_WEAK):
        return True
    return body_len < _CHALLENGE_EMPTY_BODY and any(sig in haystack for sig in _CHALLENGE_GENERIC)


# PubMed/PMC n'exposent pas le DOI dans l'URL et bloquent les IP datacenter
# derrière un reCAPTCHA. Le PMID/PMCID de l'URL suffit pour retrouver le DOI.
_PUBMED_HOSTS = ("pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov")
_NCBI_IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"


def _extract_pubmed_id(url: str) -> str | None:
    """Return the PMID or PMCID from a PubMed/PMC URL, else None."""
    host = (urlparse(url).hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in _PUBMED_HOSTS):
        return None
    m = re.search(r"/(PMC\d+)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r"/(\d{6,9})(?:[/?#]|$)", url)
    return m.group(1) if m else None


async def resolve_doi_from_pubmed(url: str) -> str | None:
    """URL PubMed/PMC → DOI via le convertisseur d'identifiants NCBI.

    Rebranche tout le pipeline Crossref (métadonnées *et* références) sur les
    liens PubMed, que le scraping ne peut pas exploiter depuis un datacenter.
    Never raises.
    """
    pubmed_id = _extract_pubmed_id(url)
    if not pubmed_id:
        return None
    api_url = f"{_NCBI_IDCONV}?ids={pubmed_id}&format=json"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(api_url)
        if r.status_code != 200:
            return None
        records = r.json().get("records") or []
        if not records:
            return None
        doi = records[0].get("doi")
        return doi.lower() if doi else None
    except Exception as e:
        logger.debug("NCBI id-conversion failed for url=%s: %s", url, e)
        return None


def _extract_pii(url: str) -> str | None:
    """Return the Elsevier PII from a ScienceDirect/Elsevier URL.

    Ex. https://www.sciencedirect.com/science/article/abs/pii/S0165032717310960
    → ``S0165032717310960``. Ces pages bloquent le scraping (anti-bot), mais
    Crossref indexe le PII brut comme ``alternative-id`` — vérifié : la requête
    ``works?filter=alternative-id:<PII>`` retourne bien l'article.
    """
    host = (urlparse(url).hostname or "").lower()
    if not (host.endswith("sciencedirect.com") or host.endswith("elsevier.com")):
        return None
    m = re.search(r"/pii/(S\d{15}[\dX])", url, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _parse_crossref_work(data: dict) -> ExtractedMetadata:
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
    container_titles = data.get("container-title") or []
    return ExtractedMetadata(
        title=title,
        authors=authors,
        published_at=published_at,
        description=abstract,
        citations_count=citations_count,
        journal=(str(container_titles[0])[:300] if container_titles else None),
        volume=(str(data["volume"])[:50] if data.get("volume") else None),
        pages=(str(data["page"])[:50] if data.get("page") else None),
        publisher=(str(data["publisher"])[:300] if data.get("publisher") else None),
        doi=((data.get("DOI") or "").lower() or None),
    )


async def crossref_lookup(doi: str) -> ExtractedMetadata | None:
    """Lookup metadata for a bare DOI via Crossref. Never raises.

    Public — reusable from other modules (imports pipeline uses it to
    backfill metadata for refs harvested from a page's References section).
    """
    url = f"https://api.crossref.org/works/{doi}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        return _parse_crossref_work(r.json().get("message", {}))
    except Exception as e:
        logger.debug("Crossref lookup failed for doi=%s: %s", doi, e)
        return None


# Compat interne : ancienne API privée conservée pour éviter de toucher extract().
_crossref = crossref_lookup


async def get_crossref_references(doi: str) -> list[SemanticScholarRef] | None:
    """Refs citees par ``doi`` via le depot Crossref de l'editeur. Never raises.

    Fallback de l'etage Semantic Scholar : Elsevier fait elider ses references
    chez S2 (`data: null`, "elided by the publisher") mais les depose chez
    Crossref (`works/{doi}` -> tableau `reference`). Retourne None si le DOI
    est inconnu ou si l'editeur n'a pas depose ses references.
    """
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{doi}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        raw_refs = r.json().get("message", {}).get("reference") or []
        if not raw_refs:
            return None
        refs = [_crossref_reference_item_to_ref(item) for item in raw_refs]
        await resolve_missing_titles(refs)
        for ref in refs:
            # Derniers recours, dans l'ordre du moins mauvais : la citation
            # brute identifie au moins l'oeuvre, le nom de revue presque pas.
            if not ref.title:
                ref.title = (ref.raw_text or ref.journal or "")[:300] or None
        return refs
    except Exception as e:
        logger.debug("Crossref references lookup failed for doi=%s: %s", doi, e)
        return None


def _crossref_reference_item_to_ref(item: dict) -> SemanticScholarRef:
    ref_doi = (item.get("DOI") or "").lower() or None
    title = (
        item.get("article-title")
        or item.get("volume-title")
        # Livres : Elsevier depose le titre dans series-title
        or item.get("series-title")
    )
    if title:
        title = str(title).strip()[:300]
    journal = item.get("journal-title")
    unstructured = item.get("unstructured")
    year_raw = item.get("year")
    try:
        year = int(str(year_raw)[:4]) if year_raw else None
    except ValueError:
        year = None
    return SemanticScholarRef(
        title=title,
        authors=item.get("author"),
        year=year,
        doi=ref_doi,
        url=f"https://doi.org/{ref_doi}" if ref_doi else None,
        raw_text=(str(unstructured).strip()[:1000] if unstructured else None),
        journal=(str(journal).strip()[:300] if journal else None),
    )


# Crossref accepte plusieurs `filter=doi:` dans une meme requete (OR logique).
# 50 tient largement sous la limite de longueur d'URL et evite de multiplier
# les allers-retours sur une bibliographie de 200 references.
_DOI_BATCH_SIZE = 50


async def resolve_missing_titles(refs: list[SemanticScholarRef]) -> None:
    """Complete in-place les refs sans titre, par resolution de leur DOI.

    Beaucoup d'editeurs (Springer, BMC, Wiley) ne deposent chez Crossref que la
    citation brute — aucun champ structure. On ne devine pas le titre en
    decoupant cette chaine : on interroge Crossref sur le DOI de la reference,
    qui rend le titre exact tel que l'editeur du papier cite l'a lui-meme
    depose. Exact plutot qu'heuristique, et valable pour n'importe quel
    editeur.

    Ne leve jamais : une resolution qui echoue laisse la ref telle quelle.
    """
    todo = {r.doi: r for r in refs if r.doi and not r.title}
    if not todo:
        return
    dois = list(todo)
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            for start in range(0, len(dois), _DOI_BATCH_SIZE):
                batch = dois[start : start + _DOI_BATCH_SIZE]
                params = {
                    "filter": ",".join(f"doi:{d}" for d in batch),
                    "rows": str(len(batch)),
                    "select": "DOI,title,author,issued",
                }
                r = await client.get("https://api.crossref.org/works", params=params)
                if r.status_code != 200:
                    continue
                for item in r.json().get("message", {}).get("items") or []:
                    ref = todo.get((item.get("DOI") or "").lower())
                    if ref is None:
                        continue
                    _apply_crossref_work_to_ref(item, ref)
    except Exception as e:
        logger.debug("Crossref batch title resolution failed: %s", e)


def _apply_crossref_work_to_ref(item: dict, ref: SemanticScholarRef) -> None:
    titles = item.get("title") or []
    if titles:
        ref.title = str(titles[0]).strip()[:300]
    authors_raw = item.get("author") or []
    authors = ", ".join(
        f"{a.get('family', '')} {a.get('given', '')[:1]}.".strip()
        for a in authors_raw[:5]
        if a.get("family")
    )
    if authors:
        ref.authors = authors
    if not ref.year:
        date_parts = (item.get("issued") or {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            with contextlib.suppress(TypeError, ValueError):
                ref.year = int(date_parts[0][0])


async def resolve_doi_from_pii(url: str) -> str | None:
    """URL ScienceDirect/Elsevier → DOI via le PII et Crossref. Never raises.

    Permet a l'etage Semantic Scholar du pipeline d'import de fonctionner sur
    les URLs ScienceDirect (aucun DOI dans l'URL, scraping bloque anti-bot).
    """
    pii = _extract_pii(url)
    if not pii:
        return None
    api_url = f"https://api.crossref.org/works?filter=alternative-id:{pii}&rows=1"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(api_url)
        if r.status_code != 200:
            return None
        items = r.json().get("message", {}).get("items") or []
        if not items:
            return None
        doi = items[0].get("DOI")
        return doi.lower() if doi else None
    except Exception as e:
        logger.debug("Crossref DOI-from-PII failed for url=%s: %s", url, e)
        return None


_S2_PAPER_BY_URL = "https://api.semanticscholar.org/graph/v1/paper/URL:{url}"
_CROSSREF_BY_URI = "https://api.crossref.org/works?filter=uri:{url}&rows=1"

# Une meme URL est resolue plusieurs fois par requete d'import (metadonnees puis
# references). Les deux API sont rate-limitees ; le cache evite d'en depenser le
# quota pour rien. Vie du process, aucune invalidation : un DOI ne change pas.
_url_doi_cache: dict[str, str | None] = {}


async def _s2_doi_by_url(url: str) -> str | None:
    api_url = _S2_PAPER_BY_URL.format(url=quote(url, safe=""))
    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
        r = await client.get(api_url, params={"fields": "externalIds"})
    if r.status_code != 200:
        return None
    doi = (r.json().get("externalIds") or {}).get("DOI")
    return doi.lower() if doi else None


async def _crossref_doi_by_uri(url: str) -> str | None:
    api_url = _CROSSREF_BY_URI.format(url=quote(url, safe=""))
    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
        r = await client.get(api_url)
    if r.status_code != 200:
        return None
    items = r.json().get("message", {}).get("items") or []
    if not items:
        return None
    doi = items[0].get("DOI")
    return doi.lower() if doi else None


async def resolve_doi_from_url(url: str) -> str | None:
    """N'importe quelle URL d'article → DOI, sans connaissance de l'editeur.

    Remplace les resolutions par site (Nature, bioRxiv, ScienceDirect…) : ce
    sont les index bibliographiques qui savent quelle URL designe quel article,
    pas nous. Semantic Scholar d'abord (couverture d'URL la plus large), puis
    Crossref `filter=uri:` qui indexe les URLs de resolution deposees par les
    editeurs. Never raises.
    """
    if url in _url_doi_cache:
        return _url_doi_cache[url]

    doi: str | None = None
    for resolver in (_s2_doi_by_url, _crossref_doi_by_uri):
        try:
            doi = await resolver(url)
        except Exception as e:
            logger.debug("%s failed for url=%s: %s", resolver.__name__, url, e)
            continue
        if doi:
            break

    _url_doi_cache[url] = doi
    return doi


async def _crossref_by_pii(pii: str) -> ExtractedMetadata | None:
    url = f"https://api.crossref.org/works?filter=alternative-id:{pii}&rows=1"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        items = r.json().get("message", {}).get("items") or []
        if not items:
            return None
        return _parse_crossref_work(items[0])
    except Exception as e:
        logger.debug("Crossref lookup failed for pii=%s: %s", pii, e)
        return None


async def _html_scrape(url: str) -> ExtractedMetadata | None:
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(url)
        # 403/429 : le serveur a compris la demande et l'a refusée. 503 est
        # ambigu (panne ou obstacle) mais les protections anti-bot s'en servent
        # massivement, et « le site n'a pas voulu répondre » reste vrai des deux.
        if r.status_code in (403, 429, 503):
            logger.info("access_blocked url=%s status=%s", url, r.status_code)
            return ExtractedMetadata(access_blocked=True)
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

        page_text = soup.get_text(separator=" ", strip=True) or None
        if _looks_like_challenge_page(str(title) if title else None, page_text):
            logger.info("challenge_page_detected url=%s title=%r", url, title)
            return ExtractedMetadata(access_blocked=True)

        if title:
            title = clean_title(title, _meta("og:site_name"), url)

        return ExtractedMetadata(
            title=title or None,
            authors=authors_raw or None,
            published_at=published_at,
            description=description or None,
            page_text=page_text,
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

    crossref_meta: ExtractedMetadata | None = None
    doi = _extract_doi(url)
    if doi:
        crossref_meta = await _crossref(doi)
    if crossref_meta is None:
        # ScienceDirect/Elsevier : pas de DOI dans l'URL et scraping bloqué
        # (anti-bot), mais le PII de l'URL est indexé par Crossref.
        pii = _extract_pii(url)
        if pii:
            crossref_meta = await _crossref_by_pii(pii)
    if crossref_meta is None:
        # PubMed/PMC : le DOI n'est pas dans l'URL et la page est protegee.
        pubmed_doi = await resolve_doi_from_pubmed(url)
        if pubmed_doi:
            crossref_meta = await _crossref(pubmed_doi)
    if crossref_meta is None:
        # Dernier recours, valable pour tout editeur : demander aux index
        # bibliographiques quel article cette URL designe.
        resolved_doi = await resolve_doi_from_url(url)
        if resolved_doi:
            crossref_meta = await _crossref(resolved_doi)
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
            # Un refus n'est signalé que s'il a réellement privé la fiche de
            # quelque chose : quand Crossref a déjà tout donné, le blocage de la
            # page d'éditeur n'a aucune conséquence et l'annoncer inquiéterait
            # pour rien.
            result.access_blocked = html_meta.access_blocked and result.title is None

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
