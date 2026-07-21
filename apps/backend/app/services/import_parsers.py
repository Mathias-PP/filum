"""Parseurs de fichiers bibliographiques → brouillons de sources.

Formats supportes : BibTeX (.bib), CSL-JSON (export Zotero), Markdown
(notes Obsidian), PDF (extraction des URLs/DOI du texte). Fonctions pures,
stdlib uniquement — le PDF est fouille via zlib (streams FlateDecode),
sans dependance d'extraction lourde.

Chaque parseur retourne des ImportedRef ; les entrees sans URL ni DOI sont
comptees dans `skipped` (le modele Source exige une URL).
"""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass, field


@dataclass
class ImportedRef:
    url: str
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    category: str = "page-web"
    # Texte brut du bloc de reference d'ou cette ref vient (Frontiers/PMC :
    # "AdlemanN. E.MenonV.BlaseyC. M. (2002). A developmental fMRI study..."
    # + DOI). Utilise en fallback LLM par-bloc quand Crossref echoue.
    # Non serialise vers l'API (usage interne pipeline uniquement).
    raw_text: str | None = None


@dataclass
class ParseResult:
    refs: list[ImportedRef] = field(default_factory=list)
    skipped: int = 0


_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>{}]+)")
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]}]+")

# Suffixes de chemin ajoutés par les éditeurs après un DOI dans leurs URLs
# (Wiley /doi/full/10.1002/xxx, T&F /doi/pdf/10.1080/yyy, Frontiers /full,
# PLOS /article, etc.). Utilisé pour normaliser le DOI extrait d'une URL.
_DOI_PATH_SUFFIXES = re.compile(r"/(?:full|abstract|pdf|epdf|epub|meta|figures|references)$", re.I)


def _doi_to_url(doi: str) -> str:
    return f"https://doi.org/{doi.rstrip('.,;')}"


def _doi_from_url(url: str) -> str | None:
    """Extract a bare DOI from any URL that embeds one.

    Handles doi.org / dx.doi.org, DOIs in publisher URL paths
    (Frontiers /articles/10.3389/…, Wiley /doi/10.1002/…, Springer
    /article/10.1007/…), and DOIs passed as query params
    (?doi=10.xxx/yyy, URL-encoded or not — common on ScienceDirect).
    Returns lowercased DOI without trailing publisher suffixes like
    ``/full`` or ``/pdf``.
    """
    from urllib.parse import unquote

    decoded = unquote(url)
    patterns = [
        r"(?:https?://)?(?:dx\.)?doi\.org/([^\s?#]+)",
        r"[?&]doi=(10\.\d{4,9}/[^\s&#]+)",
        r"/(10\.\d{4,9}/[^\s?#]+)",
    ]
    for p in patterns:
        m = re.search(p, decoded, re.IGNORECASE)
        if m:
            doi = m.group(1).strip().rstrip(".,;)/")
            doi = _DOI_PATH_SUFFIXES.sub("", doi)
            return doi.lower()
    return None


def _dedupe_key(url: str) -> str:
    """Canonical dedup key: DOI when embedded, else the normalized URL.

    Collapses e.g. ``doi.org/10.3389/fpsyg.2018.01561`` and the Frontiers
    canonical URL ``frontiersin.org/…/10.3389/fpsyg.2018.01561/full`` to
    the same ref, since they resolve to the same article.
    """
    doi = _doi_from_url(url)
    if doi:
        return f"doi:{doi}"
    return url.rstrip("/").lower()


def _dedupe(refs: list[ImportedRef]) -> list[ImportedRef]:
    seen: set[str] = set()
    out: list[ImportedRef] = []
    for ref in refs:
        key = _dedupe_key(ref.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


# --- BibTeX -----------------------------------------------------------------

_BIBTEX_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", re.IGNORECASE)

_CATEGORY_BY_BIBTEX_TYPE = {
    "article": "article-scientifique",
    "inproceedings": "article-scientifique",
    "incollection": "article-scientifique",
    "phdthesis": "article-scientifique",
    "mastersthesis": "article-scientifique",
    "techreport": "communique",
    "book": "livre",
    "inbook": "livre",
    "booklet": "livre",
    "unpublished": "preprint",
}


def _parse_bibtex_fields(body: str) -> dict[str, str]:
    """Parse `champ = {valeur}` / `champ = "valeur"` / `champ = 1234`."""
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        m = re.match(r"\s*,?\s*(\w+)\s*=\s*", body[i:])
        if not m:
            break
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        ch = body[i]
        if ch == "{":
            depth = 0
            start = i + 1
            while i < n:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            value = body[start:i]
            i += 1
        elif ch == '"':
            end = body.find('"', i + 1)
            if end == -1:
                break
            value = body[i + 1 : end]
            i = end + 1
        else:
            m2 = re.match(r"[^,]*", body[i:])
            value = m2.group(0) if m2 else ""
            i += len(value)
        fields[name] = re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()
    return fields


def parse_bibtex(text: str) -> ParseResult:
    result = ParseResult()
    for m in _BIBTEX_ENTRY_RE.finditer(text):
        entry_type = m.group(1).lower()
        if entry_type in ("comment", "preamble", "string"):
            continue
        # Corps de l'entree : jusqu'a l'accolade fermante equilibree.
        start = text.index("{", m.start())
        depth = 0
        end = start
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        body = text[m.end() : end]
        fields = _parse_bibtex_fields(body)
        url = fields.get("url") or (_doi_to_url(fields["doi"]) if fields.get("doi") else None)
        if not url:
            result.skipped += 1
            continue
        year: int | None = None
        if fields.get("year", "").strip()[:4].isdigit():
            year = int(fields["year"].strip()[:4])
        result.refs.append(
            ImportedRef(
                url=url,
                title=fields.get("title") or None,
                authors=fields.get("author", "").replace(" and ", ", ") or None,
                year=year,
                category=_CATEGORY_BY_BIBTEX_TYPE.get(entry_type, "page-web"),
            )
        )
    result.refs = _dedupe(result.refs)
    return result


# --- CSL-JSON (export Zotero) -----------------------------------------------

_CATEGORY_BY_CSL_TYPE = {
    "article-journal": "article-scientifique",
    "paper-conference": "article-scientifique",
    "thesis": "article-scientifique",
    "report": "communique",
    "article-newspaper": "article-presse",
    "article-magazine": "article-presse",
    "book": "livre",
    "chapter": "livre",
    "webpage": "page-web",
    "post-weblog": "blog",
    "broadcast": "documentaire",
    "interview": "interview",
    "song": "podcast",
    "motion_picture": "documentaire",
}


def parse_csl_json(text: str) -> ParseResult:
    result = ParseResult()
    try:
        data = json.loads(text)
    except ValueError:
        return result
    items = data if isinstance(data, list) else data.get("items", [])
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("URL") or (_doi_to_url(item["DOI"]) if item.get("DOI") else None)
        if not url:
            result.skipped += 1
            continue
        authors = None
        if isinstance(item.get("author"), list):
            names = []
            for a in item["author"]:
                if not isinstance(a, dict):
                    continue
                family = a.get("family", "")
                given = a.get("given", "")
                name = f"{family} {given}".strip() or a.get("literal", "")
                if name:
                    names.append(name)
            authors = ", ".join(names) or None
        year = None
        issued = item.get("issued")
        if isinstance(issued, dict):
            parts = issued.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                try:
                    year = int(parts[0][0])
                except (TypeError, ValueError):
                    year = None
        result.refs.append(
            ImportedRef(
                url=url,
                title=item.get("title") or None,
                authors=authors,
                year=year,
                category=_CATEGORY_BY_CSL_TYPE.get(str(item.get("type", "")), "page-web"),
            )
        )
    result.refs = _dedupe(result.refs)
    return result


# --- Markdown (Obsidian) ----------------------------------------------------

_MD_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MD_IMAGE_RE = re.compile(r"\!\[[^\]]*\]\((https?://[^)\s]+)\)")


def parse_markdown(text: str) -> ParseResult:
    result = ParseResult()
    linked_urls: set[str] = set()
    for m in _MD_LINK_RE.finditer(text):
        title, url = m.group(1).strip(), m.group(2)
        linked_urls.add(url)
        result.refs.append(ImportedRef(url=url, title=title or None))
    # Les images ne sont pas des sources : leurs URLs sont exclues du scan nu.
    for m in _MD_IMAGE_RE.finditer(text):
        linked_urls.add(m.group(1))
    # URLs nues (hors liens deja captures)
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:")
        if url not in linked_urls:
            result.refs.append(ImportedRef(url=url))
    # DOIs nus sans URL
    for m in _DOI_RE.finditer(text):
        candidate = _doi_to_url(m.group(1))
        result.refs.append(ImportedRef(candidate, category="article-scientifique"))
    result.refs = _dedupe(result.refs)
    return result


# --- PDF --------------------------------------------------------------------


def _pdf_text_chunks(data: bytes) -> list[str]:
    """Zones lisibles d'un PDF : octets bruts + streams FlateDecode degonfles."""
    chunks = [data.decode("latin-1", errors="ignore")]
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end].rstrip(b"\r\n")
        try:
            chunks.append(zlib.decompress(raw).decode("latin-1", errors="ignore"))
        except zlib.error:
            continue
    return chunks


def parse_pdf(data: bytes) -> ParseResult:
    result = ParseResult()
    for chunk in _pdf_text_chunks(data):
        for m in _URL_RE.finditer(chunk):
            url = m.group(0).rstrip(".,;:)")
            # Les operateurs PDF collent parfois du bruit apres l'URL ; on
            # coupe au premier caractere improbable dans une URL.
            url = re.split(r"[\\(]", url)[0]
            if len(url) > 12:
                result.refs.append(ImportedRef(url=url))
        for m in _DOI_RE.finditer(chunk):
            doi = re.split(r"[\\(]", m.group(1))[0]
            result.refs.append(ImportedRef(_doi_to_url(doi), category="article-scientifique"))
    result.refs = _dedupe(result.refs)
    return result


# --- Detection --------------------------------------------------------------


def detect_format(filename: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".bib") or name.endswith(".bibtex"):
        return "bibtex"
    if name.endswith(".json"):
        return "csl-json"
    if name.endswith(".md") or name.endswith(".markdown"):
        return "markdown"
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return "pdf"
    head = data[:2000].decode("utf-8", errors="ignore").lstrip()
    if head.startswith(("[", "{")):
        return "csl-json"
    if re.search(r"@\w+\s*\{", head):
        return "bibtex"
    return "markdown"


def parse_file(filename: str | None, data: bytes, forced_format: str | None = None) -> ParseResult:
    fmt = forced_format or detect_format(filename, data)
    if fmt == "pdf":
        return parse_pdf(data)
    text = data.decode("utf-8", errors="replace")
    if fmt == "bibtex":
        return parse_bibtex(text)
    if fmt == "csl-json":
        return parse_csl_json(text)
    return parse_markdown(text)
