"""Import de fichiers bibliographiques (BibTeX, CSL-JSON, Markdown, PDF).

L'endpoint ne cree rien en base : il parse le fichier et retourne des
brouillons de sources que le frontend injecte dans le flux multi-liens
existant (l'utilisateur valide chaque brouillon avant creation).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.v1.endpoints.cards import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.services.import_parsers import (
    ImportedRef,
    ParseResult,
    _doi_to_url,
    detect_format,
    parse_file,
    parse_markdown,
)
from app.services.llm import LlmBiblioRef, parse_bibliography

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
    by_url = {ref.url.rstrip("/").lower(): ref for ref in base.refs}
    skipped = base.skipped
    for ref in llm_refs:
        url = ref.url or (_doi_to_url(ref.doi) if ref.doi else None)
        if not url or not url.startswith(("http://", "https://")):
            skipped += 1
            continue
        key = url.rstrip("/").lower()
        existing = by_url.get(key)
        if existing is None:
            by_url[key] = ImportedRef(
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
    return ParseResult(refs=list(by_url.values()), skipped=skipped)


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
