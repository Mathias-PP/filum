"""Import de fichiers bibliographiques (BibTeX, CSL-JSON, Markdown, PDF).

L'endpoint ne cree rien en base : il parse le fichier et retourne des
brouillons de sources que le frontend injecte dans le flux multi-liens
existant (l'utilisateur valide chaque brouillon avant creation).
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.v1.endpoints.cards import get_current_user
from app.core.rate_limit import limiter
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.extractors.url_extractor import extract as extract_url_metadata
from app.models.user import User
from app.services.import_parsers import (
    ImportedRef,
    ParseResult,
    _dedupe_key,
    _doi_to_url,
    detect_format,
    parse_file,
    parse_markdown,
)
from app.services.llm import LlmBiblioRef, parse_bibliography

logger = logging.getLogger(__name__)

router = APIRouter(tags=["imports"])

MAX_FILE_SIZE = 5 * 1024 * 1024

_FORMATS = {"bibtex", "csl-json", "markdown", "pdf"}

_AUTHOR_KIND_BY_CATEGORY = {
    "article-scientifique": "chercheur",
    "preprint": "chercheur",
    "article-presse": "media",
    "communique": "institution-publique",
}

_FORMAT_BY_CATEGORY = {
    "documentaire": "video",
    "podcast": "audio",
}


class ImportedSourceDraft(BaseModel):
    url: str
    title: str | None = None
    authors: str | None = None
    published_at: str | None = None
    format: str = "texte"
    category: str = "page-web"
    author_kind: str = "individu"


class ImportParseResponse(BaseModel):
    sources: list[ImportedSourceDraft]
    skipped: int
    format_detected: str


def _to_draft(ref: ImportedRef) -> ImportedSourceDraft:
    return ImportedSourceDraft(
        url=ref.url,
        title=ref.title,
        authors=ref.authors,
        published_at=f"{ref.year}-01-01T00:00:00Z" if ref.year else None,
        format=_FORMAT_BY_CATEGORY.get(ref.category, "texte"),
        category=ref.category,
        author_kind=_AUTHOR_KIND_BY_CATEGORY.get(ref.category, "individu"),
    )


@router.post("/import/parse", response_model=ImportParseResponse)
@limiter.limit("30/hour")
async def parse_import_file(
    request: Request,
    file: UploadFile,
    format: str | None = None,
    current_user: User = Depends(get_current_user),
):
    if format is not None and format not in _FORMATS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"Unknown format '{format}'. Expected one of: {sorted(_FORMATS)}",
            },
        )
    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "message": "File exceeds 5 MB limit"},
        )
    detected = format or detect_format(file.filename, data)
    result = parse_file(file.filename, data, forced_format=detected)
    return ImportParseResponse(
        sources=[_to_draft(ref) for ref in result.refs],
        skipped=result.skipped,
        format_detected=detected,
    )


class ImportPasteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


def _merge_llm_refs(base: ParseResult, llm_refs: list[LlmBiblioRef]) -> ParseResult:
    """Fusionne les refs LLM avec le parsing déterministe (clé = URL).

    Le déterministe fait foi pour les URLs ; le LLM enrichit (titre, auteurs,
    année, catégorie) et ajoute les refs dont l'URL/DOI n'a pas été capté.
    Les refs LLM sans lien sont comptées dans skipped (Source exige une URL).
    """
    by_key = {_dedupe_key(ref.url): ref for ref in base.refs}
    skipped = base.skipped
    for ref in llm_refs:
        url = ref.url or (_doi_to_url(ref.doi) if ref.doi else None)
        if not url or not url.startswith(("http://", "https://")):
            skipped += 1
            continue
        key = _dedupe_key(url)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = ImportedRef(
                url=url,
                title=ref.title,
                authors=ref.authors,
                year=ref.year,
                category=ref.category.value if ref.category else "page-web",
            )
            continue
        if not existing.title:
            existing.title = ref.title
        if not existing.authors:
            existing.authors = ref.authors
        if not existing.year:
            existing.year = ref.year
        if existing.category == "page-web" and ref.category:
            existing.category = ref.category.value
    return ParseResult(refs=list(by_key.values()), skipped=skipped)


@router.post("/import/paste", response_model=ImportParseResponse)
@limiter.limit("30/hour")
async def parse_pasted_bibliography(
    request: Request,
    payload: ImportPasteRequest,
    current_user: User = Depends(get_current_user),
):
    result = parse_markdown(payload.text)
    llm_refs = await parse_bibliography(payload.text)
    if llm_refs:
        result = _merge_llm_refs(result, llm_refs)
    return ImportParseResponse(
        sources=[_to_draft(ref) for ref in result.refs],
        skipped=result.skipped,
        format_detected="texte-libre",
    )


# --- Import depuis l'URL d'un contenu (article, PDF, page HTML) ------------
#
# Un cran au-dessus du paste : au lieu de coller le texte d'une biblio,
# l'utilisateur donne l'URL d'un contenu (un article, un billet, une video
# avec des liens sortants) et Philum :
#   1. extrait les metadonnees du contenu (titre, description, auteurs) via
#      le meme pipeline que `/sources/extract`
#   2. isole la section References de la page si presente (heuristique de
#      selecteurs CSS courants chez les editeurs)
#   3. passe le texte a `parse_bibliography` (LLM) + `parse_markdown` (regex)
#      pour extraire la liste des sources citees
#   4. retourne un draft de fiche complet a valider par l'utilisateur

_REFERENCES_SELECTORS = (
    # Frontiers, PubMed Central, JATS-like
    "section[id*='references' i]",
    "div[id*='references' i]",
    "ol[class*='references' i]",
    "ul[class*='references' i]",
    "section[id*='bibliograph' i]",
    "div[id*='bibliograph' i]",
    # Nature, generic scholarly
    "section[data-title='References']",
    "section[aria-labelledby*='references' i]",
    "div.ref-list",
    "ol.ref-list",
    "ol.references",
    "ul.references",
    # arXiv abstract page has none, PDF only; the endpoint stays best-effort.
)

# Cap pour eviter d'envoyer 500 kB de HTML au LLM (couteux + rate-limit).
_REFS_TEXT_MAX = 60_000
# Fetch cap sur le HTML brut : 3 MB, evite les mega-pages
_HTML_MAX = 3 * 1024 * 1024
_FETCH_TIMEOUT = 10.0

_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}


class ImportFromUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ImportedCardDraft(BaseModel):
    title: str | None = None
    description: str | None = None
    content_url: str


class ImportFromUrlResponse(BaseModel):
    card: ImportedCardDraft
    sources: list[ImportedSourceDraft]
    skipped: int
    references_section_found: bool
    fetch_status: str  # "ok" | "unreachable" | "not_html"


def _extract_references_text(html: str) -> tuple[str, bool]:
    """Return (text, found_dedicated_section).

    Cherche une section References dans le HTML via une short-list de
    selecteurs. Si aucune, retourne le texte de la page nettoye (le LLM
    fera au mieux). Retire systematiquement script/style/noscript/svg
    (bruit + coute cher au LLM) et, pour le fallback body, aussi
    nav/header/footer/aside (chrome UI sans valeur bibliographique).
    Le texte est cape a `_REFS_TEXT_MAX` chars.
    """
    soup = BeautifulSoup(html, "lxml")
    # Removal universel : JS/CSS et vecteurs graphiques rendent le
    # get_text() ILLISIBLE et coutent 3x plus cher au LLM. A supprimer
    # meme dans une section References dediee au cas ou elle en contient.
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()
    for selector in _REFERENCES_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if len(text) >= 80:  # eviter les sections quasi-vides
                return text[:_REFS_TEXT_MAX], True
    # Fallback: page entiere, mais on retire aussi le chrome UI qui n'a
    # aucune valeur bibliographique (menus, header/footer, sidebars).
    for tag in soup.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()
    body = soup.find("body")
    text = body.get_text(separator="\n", strip=True) if body else soup.get_text(strip=True)
    return text[:_REFS_TEXT_MAX], False


@router.post("/import/from-content-url", response_model=ImportFromUrlResponse)
@limiter.limit("5/hour")
async def parse_content_url(
    request: Request,
    payload: ImportFromUrlRequest,
    current_user: User = Depends(get_current_user),
):
    """URL d'un contenu -> draft de fiche complet (titre + sources citees).

    Rate-limit 5/heure (extraction LLM + fetch reseau). Auth requise.
    SSRF-safe via assert_url_is_safe.
    """
    url = payload.url.strip()
    try:
        assert_url_is_safe(url)
    except UnsafeUrlError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "unsafe_url", "message": str(e)},
        ) from e

    # 1. Metadata du contenu (titre, description, auteurs) - reuse url_extractor
    try:
        meta = await extract_url_metadata(url)
    except Exception as e:
        logger.warning("extract_url_metadata failed for %s: %s", url, e)
        meta = None

    # 2. Fetch le HTML pour la section references. On distingue trois etats
    # pour donner un feedback UX explicite : ok / unreachable (timeout, DNS,
    # 4xx/5xx) / not_html (PDF, image, redirection JSON API).
    html: str | None = None
    fetch_status = "unreachable"
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_FETCH_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(url)
        if r.status_code == 200:
            if "text/html" in r.headers.get("content-type", ""):
                html = r.text[:_HTML_MAX]
                fetch_status = "ok"
            else:
                fetch_status = "not_html"
    except Exception as e:
        logger.warning("fetch failed for %s: %s", url, e)

    refs_text = ""
    refs_section_found = False
    if html:
        refs_text, refs_section_found = _extract_references_text(html)

    # 3. Extraction hybride regex + LLM sur le texte des references
    result = parse_markdown(refs_text) if refs_text else ParseResult()
    if refs_text:
        llm_refs = await parse_bibliography(refs_text)
        if llm_refs:
            result = _merge_llm_refs(result, llm_refs)

    # Retire la ref pointant vers le contenu lui-meme (le contenu ne cite
    # pas lui-meme, et la fiche a deja content_url = url).
    self_key = _dedupe_key(url)
    result.refs = [ref for ref in result.refs if _dedupe_key(ref.url) != self_key]

    card = ImportedCardDraft(
        title=meta.title if meta else None,
        description=meta.description if meta else None,
        content_url=url,
    )
    return ImportFromUrlResponse(
        card=card,
        sources=[_to_draft(ref) for ref in result.refs],
        skipped=result.skipped,
        references_section_found=refs_section_found,
        fetch_status=fetch_status,
    )
