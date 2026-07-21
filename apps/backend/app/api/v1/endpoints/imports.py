"""Import de fichiers bibliographiques (BibTeX, CSL-JSON, Markdown, PDF).

L'endpoint ne cree rien en base : il parse le fichier et retourne des
brouillons de sources que le frontend injecte dans le flux multi-liens
existant (l'utilisateur valide chaque brouillon avant creation).
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.v1.endpoints.cards import get_current_user
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.extractors.grobid import extract_pdf_references
from app.extractors.semantic_scholar import SemanticScholarRef, get_paper_references
from app.extractors.url_extractor import crossref_lookup
from app.extractors.url_extractor import extract as extract_url_metadata
from app.models.user import User
from app.services.import_parsers import (
    ImportedRef,
    ParseResult,
    _dedupe,
    _dedupe_key,
    _doi_from_url,
    _doi_to_url,
    detect_format,
    parse_file,
    parse_markdown,
)
from app.services.llm import (
    LlmBiblioRef,
    classify_url_type,
    parse_bibliography,
    parse_reference_block,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["imports"])

MAX_FILE_SIZE = 5 * 1024 * 1024

_FORMATS = {"bibtex", "csl-json", "markdown", "pdf", "docx", "html"}

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
    # Classification LLM du type d'URL : 'source' | 'promo' | 'social' | 'other'.
    # None si LLM off / non appele. Le frontend affiche un badge et l'user coche.
    classification: str | None = None


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
        classification=ref.classification,
    )


@router.post("/import/parse", response_model=ImportParseResponse)
# Rate-limit retire (phase test/pre-produit) : les endpoints d'import sont
# auth-only, on veut pouvoir iterer librement. A reintroduire si abus.
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
    if detected == "pdf":
        # GROBID segmente la biblio du PDF en refs structurees (titre, auteurs,
        # annee, DOI) — bien mieux que le scan regex, qui rate les refs sans
        # URL/DOI dans le texte. Fusion : les refs GROBID (titrees) passent
        # d'abord, la dedup par DOI absorbe les doublons du scan regex.
        # Indisponible (Space endormi, timeout) → refs regex seules.
        grobid_refs = await extract_pdf_references(data)
        if grobid_refs:
            result.refs = _dedupe([*grobid_refs, *result.refs])
    # PDF/Markdown ne contiennent souvent que des DOIs nus sans metadata.
    # BibTeX/CSL-JSON ont deja tout : le backfill est un no-op sur les refs
    # deja completes (garde `title AND authors AND year`).
    await _backfill_crossref_metadata(result.refs)
    return ImportParseResponse(
        sources=[_to_draft(ref) for ref in result.refs],
        skipped=result.skipped,
        format_detected=detected,
    )


class ImportPasteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


# --- Crossref backfill : enrichit les refs avec DOI mais sans metadata ----
#
# Le pipeline regex + LLM peut retourner des refs `{url: "https://doi.org/…"}`
# sans title/authors/year : soit parce que le LLM a echoue (texte trop bruite,
# format Frontiers avec noms colles, timeout), soit parce que le regex a
# capture des DOIs nus dans le fallback body. Crossref indexe TOUT DOI de
# journal avec metadata canonique (title, authors, year, citations_count).
# Un backfill parallel est deterministe, rapide (< 20s pour 150 refs avec
# Semaphore(10)), gratuit et sans hallucination.

_CROSSREF_CONCURRENCY = 10


async def _backfill_one_crossref(ref: ImportedRef, sem: asyncio.Semaphore) -> None:
    """Enrichit `ref` in-place via Crossref si un DOI est extractible."""
    if ref.title and ref.authors and ref.year:
        return  # deja complet, skip
    doi = _doi_from_url(ref.url)
    if not doi:
        return
    async with sem:
        meta = await crossref_lookup(doi)
    if meta is None:
        return
    if not ref.title and meta.title:
        ref.title = meta.title
    if not ref.authors and meta.authors:
        ref.authors = meta.authors
    if not ref.year and meta.published_at:
        # published_at format YYYY-MM-DD.
        year_str = meta.published_at[:4]
        if year_str.isdigit():
            ref.year = int(year_str)
    # Crossref = journal DOI dans 99% des cas -> article scientifique.
    if ref.category == "page-web":
        ref.category = "article-scientifique"


async def _backfill_crossref_metadata(refs: list[ImportedRef]) -> None:
    """Enrichit en parallele les refs avec DOI mais sans metadata complete."""
    if not refs:
        return
    sem = asyncio.Semaphore(_CROSSREF_CONCURRENCY)
    await asyncio.gather(*(_backfill_one_crossref(ref, sem) for ref in refs))
    # 2e passe a concurrence reduite : sur 145 refs, ~10 lookups echouent de
    # maniere transitoire (timeout sous concurrence 10) et les trous changent
    # a chaque run — un retry sequentiel-ish les recupere quasi tous.
    remaining = [r for r in refs if not (r.title and r.authors) and _doi_from_url(r.url)]
    if remaining:
        retry_sem = asyncio.Semaphore(2)
        await asyncio.gather(*(_backfill_one_crossref(ref, retry_sem) for ref in remaining))


# --- Semantic Scholar : etage 0 quand le contenu a un DOI extractible ------
#
# Quand l'URL du contenu contient un DOI (Frontiers, Nature, Elsevier /
# ScienceDirect, Wiley, T&F, arXiv, etc.), Semantic Scholar peut donner
# directement la liste des refs citees avec metadata complet, en 1 requete
# API gratuite, sans scraping HTML ni LLM. C'est la voie royale.
#
# Couverture Elsevier / ScienceDirect via un accord d'ingestion S2, ce que
# ni Crossref ni un scraping direct ne peuvent atteindre (anti-bot).
#
# Le pipeline HTML classique tourne quand meme apres (regex + LLM sur la
# page) pour completer : parfois S2 rate qq refs ou est incomplet, ou la
# page a des refs sans DOI (livres) que S2 n'expose pas.


def _s2_ref_to_imported_ref(s2_ref: SemanticScholarRef) -> ImportedRef | None:
    """Convertit une SemanticScholarRef → ImportedRef. None si pas d'URL."""
    if not s2_ref.url:
        # Livre / chapitre sans DOI : garde-la pour edition manuelle (url="")
        # SEULEMENT si on a titre + auteurs (sinon vraiment inutile).
        if s2_ref.title and s2_ref.authors:
            return ImportedRef(
                url="",
                title=s2_ref.title,
                authors=s2_ref.authors,
                year=s2_ref.year,
                category="article-scientifique",
            )
        return None
    return ImportedRef(
        url=s2_ref.url,
        title=s2_ref.title,
        authors=s2_ref.authors,
        year=s2_ref.year,
        category="article-scientifique",
    )


def _merge_s2_refs(base: ParseResult, s2_refs: list[SemanticScholarRef]) -> ParseResult:
    """Injecte les refs S2 dans le ParseResult (deja bootstrappe par regex+LLM).

    Cle de dedup : DOI (via _dedupe_key). Si une ref S2 apparait avec le meme
    DOI qu'une ref existante, on ecrase avec les valeurs S2 (S2 est plus
    fiable que le scraping HTML). Sinon on ajoute.
    """
    by_key = {_dedupe_key(ref.url): ref for ref in base.refs if ref.url}
    skipped = base.skipped
    for s2 in s2_refs:
        imported = _s2_ref_to_imported_ref(s2)
        if imported is None:
            skipped += 1
            continue
        if not imported.url:
            # Ref sans URL mais avec titre+auteurs : on l'ajoute avec key unique
            key = f"nourl:s2:{imported.title or ''}|{imported.authors or ''}|{imported.year or ''}"
            if key not in by_key:
                by_key[key] = imported
            continue
        key = _dedupe_key(imported.url)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = imported
        else:
            # S2 est autoritaire : on enrichit les champs manquants
            if not existing.title:
                existing.title = imported.title
            if not existing.authors:
                existing.authors = imported.authors
            if not existing.year:
                existing.year = imported.year
            if existing.category == "page-web":
                existing.category = "article-scientifique"
    return ParseResult(refs=list(by_key.values()), skipped=skipped)


# --- Fallback LLM par bloc de reference ------------------------------------
#
# Quand Crossref echoue (DOI non indexe, timeout, ancien DOI '10.1207/...') OU
# quand le regex a capture une URL sans DOI et sans metadata, on peut souvent
# recuperer title/authors/year en interpretant le TEXTE de la reference. Le
# LLM global parse_bibliography analyse 60kB d'un coup et se plante sur les
# noms concatenes type Frontiers ; ici on lui passe UN SEUL bloc par appel,
# beaucoup plus fiable.

_LLM_BLOCK_CONCURRENCY = 5


async def _backfill_one_llm_block(ref: ImportedRef, sem: asyncio.Semaphore) -> None:
    """Enrichit ``ref`` in-place via un mini-appel LLM sur son ``raw_text``."""
    if ref.title and ref.authors and ref.year:
        return  # deja complet
    if not ref.raw_text or len(ref.raw_text.strip()) < 30:
        return  # rien a analyser
    async with sem:
        meta = await parse_reference_block(ref.raw_text)
    if meta is None:
        return
    if not ref.title and meta.title:
        ref.title = meta.title
    if not ref.authors and meta.authors:
        ref.authors = meta.authors
    if not ref.year and meta.year:
        ref.year = meta.year
    if ref.category == "page-web" and meta.category:
        ref.category = meta.category.value


async def _backfill_llm_per_block(refs: list[ImportedRef]) -> None:
    """LLM par bloc, en parallele borne. No-op si LLM desactive."""
    if not refs:
        return
    sem = asyncio.Semaphore(_LLM_BLOCK_CONCURRENCY)
    await asyncio.gather(*(_backfill_one_llm_block(ref, sem) for ref in refs))


# --- LLM classifier : source vs promo vs social vs other ------------------
#
# Utilise dans /import/from-content-url : quand on colle une URL YouTube ou
# blog qui contient un melange de refs bibliographiques et de liens promo
# (livre a acheter, Patreon, TikTok), le LLM propose une classification par
# URL et l'user coche/decoche selon ses envies. Rien n'est jamais filtre
# auto -- le badge est indicatif.

_CLASSIFY_CONCURRENCY = 5


async def _classify_one_ref(ref: ImportedRef, sem: asyncio.Semaphore) -> None:
    """Renseigne ``ref.classification`` in-place via LLM (best-effort)."""
    if ref.classification is not None:
        return
    if not ref.url:
        return
    parts: list[str] = []
    if ref.title:
        parts.append(f"Titre : {ref.title}")
    if ref.authors:
        parts.append(f"Auteurs : {ref.authors}")
    context = "\n".join(parts)
    async with sem:
        result = await classify_url_type(ref.url, context)
    if result:
        ref.classification = result


async def _classify_refs(refs: list[ImportedRef]) -> None:
    """Classifie chaque ref en parallele borne. No-op si LLM off."""
    if not refs:
        return
    sem = asyncio.Semaphore(_CLASSIFY_CONCURRENCY)
    await asyncio.gather(*(_classify_one_ref(ref, sem) for ref in refs))


# Split heuristique du texte References en blocs de refs individuelles.
# Frontiers/PMC/Nature : chaque ref commence par un numero sur une ligne
# ("1\nAdlemanN. E.MenonV...(2002)...\n2\nAllanN. P...").
# APA / Chicago : refs separees par lignes vides.
# Fallback : blocs de <=800 chars separes par lignes vides.

_REF_NUMBER_SPLIT = re.compile(r"\n\s*\d+\s*\n")
_BLANK_LINE_SPLIT = re.compile(r"\n\s*\n")


def _split_references_into_blocks(refs_text: str) -> list[str]:
    """Renvoie la liste des blocs de refs individuelles.

    Preference : split par numeros de ligne (Frontiers/PMC). Fallback :
    split par lignes vides. Blocs vides ou < 20 chars filtres.
    """
    if not refs_text:
        return []
    # Prefixe un "\n" pour matcher un numero de ligne en tete
    numbered = _REF_NUMBER_SPLIT.split("\n" + refs_text)
    numbered = [b.strip() for b in numbered if b.strip()]
    if len(numbered) >= 3:
        return numbered
    # Fallback : lignes vides
    blocks = _BLANK_LINE_SPLIT.split(refs_text)
    return [b.strip() for b in blocks if len(b.strip()) >= 20]


def _assign_raw_text_to_refs(refs: list[ImportedRef], blocks: list[str]) -> None:
    """Associe a chaque ref le bloc de texte qui contient son URL/DOI.

    Pour chaque ref sans raw_text, cherche le premier bloc qui contient son
    URL exacte ou le DOI derive. Mutation in-place.
    """
    for ref in refs:
        if ref.raw_text or not ref.url:
            continue
        doi = _doi_from_url(ref.url)
        for block in blocks:
            if ref.url in block or (doi and doi in block):
                ref.raw_text = block
                break


def _merge_llm_refs(base: ParseResult, llm_refs: list[LlmBiblioRef]) -> ParseResult:
    """Fusionne les refs LLM avec le parsing déterministe (clé = URL ou identité).

    Le déterministe fait foi pour les URLs ; le LLM enrichit (titre, auteurs,
    année, catégorie) et ajoute les refs dont l'URL/DOI n'a pas été capté.

    Les refs LLM sans URL ni DOI (typique : livres, DSM-IV, chapitres) sont
    conservées avec ``url=""`` afin que l'utilisateur puisse compléter l'URL
    à la main dans la preview du frontend (ex. ISBN, WorldCat, éditeur). La
    clé de dédup pour ces refs est ``nourl:{title|authors|year}`` pour éviter
    de collapser en une seule ref les livres différents sans URL.
    """
    by_key = {_dedupe_key(ref.url): ref for ref in base.refs}
    skipped = base.skipped
    for ref in llm_refs:
        url = ref.url or (_doi_to_url(ref.doi) if ref.doi else None)
        if url and not url.startswith(("http://", "https://")):
            # URL malformee (ni http ni https) -> skip vraiment
            skipped += 1
            continue
        if url is None:
            # Ref LLM sans URL ni DOI : conserve avec url="" pour edition
            # manuelle. Skip seulement si aucune metadata utile.
            if not ref.title and not ref.authors:
                skipped += 1
                continue
            key = f"nourl:{ref.title or ''}|{ref.authors or ''}|{ref.year or ''}".lower()
            if key not in by_key:
                by_key[key] = ImportedRef(
                    url="",
                    title=ref.title,
                    authors=ref.authors,
                    year=ref.year,
                    category=ref.category.value if ref.category else "page-web",
                )
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
# Rate-limit retire (phase test/pre-produit) : auth-only, iteration libre.
async def parse_pasted_bibliography(
    request: Request,
    payload: ImportPasteRequest,
    current_user: User = Depends(get_current_user),
):
    result = parse_markdown(payload.text)
    llm_refs = await parse_bibliography(payload.text)
    if llm_refs:
        result = _merge_llm_refs(result, llm_refs)
    # Backfill Crossref pour les refs avec DOI mais sans metadata complete
    # (typique : LLM off/echoue -> URL DOI nue capturee par le regex).
    await _backfill_crossref_metadata(result.refs)
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

# Wayback Machine : fallback quand le fetch principal echoue (Cloudflare
# challenge, 403, timeout, page morte). L'API "available" repond en <1s
# avec l'URL de la snapshot la plus proche.
_WAYBACK_AVAILABLE_API = "http://archive.org/wayback/available"
_WAYBACK_TIMEOUT = 10.0


async def _try_wayback_snapshot(url: str) -> tuple[str | None, str | None]:
    """Renvoie (html, wayback_url) si Wayback a une snapshot exploitable.

    L'API archive.org/wayback/available retourne la snapshot la plus proche.
    Si oui, on fetch le HTML archive et on retourne (html, snapshot_url).
    Sinon (pas de snapshot, timeout, non-HTML) -> (None, None).
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_WAYBACK_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.get(_WAYBACK_AVAILABLE_API, params={"url": url})
        if r.status_code != 200:
            return None, None
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest", {})
        if not snap.get("available"):
            return None, None
        snapshot_url = snap.get("url")
        if not snapshot_url:
            return None, None
        # Fetch le HTML archive. Wayback renvoie le HTML original du site
        # ciblé (avec un banner Wayback injecte mais ça ne casse pas le scrape).
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_FETCH_TIMEOUT, follow_redirects=True
        ) as client:
            r2 = await client.get(snapshot_url)
        if r2.status_code == 200 and "text/html" in r2.headers.get("content-type", ""):
            return r2.text[:_HTML_MAX], snapshot_url
        return None, snapshot_url
    except Exception as e:
        logger.warning("wayback fallback failed for %s: %s", url, e)
        return None, None


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
    fetch_status: str  # "ok" | "ok_via_wayback" | "unreachable" | "not_html"
    # URL de la snapshot Wayback si le fetch principal a echoue et que Wayback
    # a permis de recuperer une version archivee. None sinon.
    wayback_url: str | None = None


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
# Rate-limit retire (phase test/pre-produit) : auth-only, iteration libre.
# A reintroduire quand on aura une metrique de cout LLM/Crossref preoccupante.
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

    # 2. Fetch le HTML pour la section references. On distingue plusieurs
    # etats pour donner un feedback UX explicite :
    #   - ok            : fetch direct reussi
    #   - ok_via_wayback: fetch direct a echoue, mais Wayback a une snapshot
    #   - unreachable   : ni le fetch direct ni Wayback ne repondent
    #   - not_html      : la reponse est un PDF / image / JSON, pas exploitable
    html: str | None = None
    fetch_status = "unreachable"
    wayback_url: str | None = None
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

    # 2.5. Fallback Wayback si le fetch direct a echoue (unreachable OU
    # not_html). L'idee : ScienceDirect / Cloudflare / 403 sur la page live
    # ont souvent une snapshot exploitable via web.archive.org.
    if html is None:
        wayback_html, wayback_url = await _try_wayback_snapshot(url)
        if wayback_html:
            html = wayback_html
            fetch_status = "ok_via_wayback"

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

    # 3.5. Semantic Scholar si le contenu a un DOI extractible : c'est la
    # source la plus fiable pour les refs scholarly (couvre ScienceDirect /
    # Elsevier, chose ni Crossref ni scraping ne peuvent atteindre).
    content_doi = _doi_from_url(url)
    if content_doi:
        s2_refs = await get_paper_references(content_doi)
        if s2_refs:
            logger.info(
                "s2_hit doi=%s refs=%d (before merge: %d)",
                content_doi,
                len(s2_refs),
                len(result.refs),
            )
            result = _merge_s2_refs(result, s2_refs)

    # Retire la ref pointant vers le contenu lui-meme (le contenu ne cite
    # pas lui-meme, et la fiche a deja content_url = url).
    self_key = _dedupe_key(url)
    result.refs = [ref for ref in result.refs if _dedupe_key(ref.url) != self_key]

    # 4. Split le texte References en blocs et associe chaque bloc a la ref
    # correspondante (via URL/DOI present dans le bloc). Utilise ensuite pour
    # le fallback LLM par-bloc si Crossref echoue.
    ref_blocks = _split_references_into_blocks(refs_text)
    _assign_raw_text_to_refs(result.refs, ref_blocks)

    # 5. Backfill Crossref pour toute ref avec DOI mais sans metadata complete.
    # Frontiers/PMC/Nature ont des sections References ou les noms d'auteurs
    # sont concatenes sans espaces (« AdlemanN. E.MenonV.BlaseyC. M... »)
    # -> Crossref donne title/authors/year/citations_count deterministes.
    await _backfill_crossref_metadata(result.refs)

    # 6. Fallback LLM par-bloc pour les refs qui ont un raw_text mais
    # toujours pas de metadata complete (Crossref echec, DOI ancien
    # non indexe, ou pas de DOI mais URL). Un mini-appel LLM par bloc,
    # bien plus fiable que l'appel global sur les 60kB concatenes.
    await _backfill_llm_per_block(result.refs)

    # 7. Classifie chaque URL (source / promo / social / other) pour la UI.
    # Rien n'est filtre auto : c'est indicatif, l'user coche a sa guise.
    await _classify_refs(result.refs)

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
        wayback_url=wayback_url,
    )


class UrlMetadataRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class UrlMetadataResponse(BaseModel):
    title: str | None = None
    description: str | None = None


@router.post("/import/url-metadata", response_model=UrlMetadataResponse)
async def url_metadata(
    request: Request,
    payload: UrlMetadataRequest,
    current_user: User = Depends(get_current_user),
):
    """Metadata legere (titre, description) d'une URL de contenu.

    Version rapide de /import/from-content-url : un seul fetch de page,
    pas d'extraction de references ni de LLM. Sert a pre-remplir le
    formulaire « Nouvelle fiche » pendant la saisie.
    """
    url = payload.url.strip()
    try:
        assert_url_is_safe(url)
    except UnsafeUrlError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "unsafe_url", "message": str(e)},
        ) from e
    try:
        meta = await extract_url_metadata(url)
    except Exception as e:
        logger.warning("extract_url_metadata failed for %s: %s", url, e)
        meta = None
    return UrlMetadataResponse(
        title=meta.title if meta else None,
        description=meta.description if meta else None,
    )
