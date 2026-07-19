"""Extraits (citations) d'une source : CRUD + suggestion IA.

La suggestion IA repère des citations *verbatim* dans le texte de la source
(alias LiteLLM `excerpt-suggest`). Anti-hallucination : chaque extrait
proposé est vérifié par recherche exacte (espaces normalisés) dans le texte
récupéré — un extrait introuvable est écarté, jamais exposé. L'emplacement
exact (offset caractère + contexte) est retourné mais non persisté :
`source_excerpts` ne stocke que le texte, retrouvable au mot près.
"""

from __future__ import annotations

import asyncio
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.sources import get_current_user
from app.core.rate_limit import limiter
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.schemas.source import SourceExcerptResponse
from app.services.llm import suggest_excerpts

router = APIRouter(prefix="/sources/{source_id}/excerpts", tags=["excerpts"])

MAX_EXCERPTS_PER_SOURCE = 10


class ExcerptCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    suggested_by_ai: bool = False


class SuggestedExcerpt(BaseModel):
    text: str
    char_offset: int
    context_before: str
    context_after: str


class ExcerptSuggestResponse(BaseModel):
    suggestions: list[SuggestedExcerpt]
    page_text_length: int
    llm_enabled: bool


async def _get_owned_source(source_id: UUID, user: User, db: AsyncSession) -> Source:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Source not found"},
        )
    card = await db.scalar(
        select(BiblioCard).where(
            BiblioCard.id == source.biblio_card_id, BiblioCard.deleted_at.is_(None)
        )
    )
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if card.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Access denied"},
        )
    return source


def verify_quote(page_text: str, quote: str) -> re.Match[str] | None:
    """Recherche exacte du passage, tolérante aux espaces/retours à la ligne."""
    quote = quote.strip()
    if len(quote) < 10:
        return None
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
    return re.search(pattern, page_text, re.IGNORECASE)


@router.post("", response_model=SourceExcerptResponse, status_code=status.HTTP_201_CREATED)
async def create_excerpt(
    source_id: UUID,
    payload: ExcerptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user, db)
    count = await db.scalar(
        select(func.count()).select_from(SourceExcerpt).where(SourceExcerpt.source_id == source.id)
    )
    if (count or 0) >= MAX_EXCERPTS_PER_SOURCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": f"Maximum {MAX_EXCERPTS_PER_SOURCE} excerpts per source",
            },
        )
    max_pos = await db.scalar(
        select(func.max(SourceExcerpt.position)).where(SourceExcerpt.source_id == source.id)
    )
    excerpt = SourceExcerpt(
        source_id=source.id,
        position=(max_pos or 0) + 1,
        text=payload.text.strip(),
        suggested_by_ai=payload.suggested_by_ai,
    )
    db.add(excerpt)
    await db.commit()
    await db.refresh(excerpt)
    return excerpt


@router.delete("/{excerpt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_excerpt(
    source_id: UUID,
    excerpt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user, db)
    excerpt = await db.scalar(
        select(SourceExcerpt).where(
            SourceExcerpt.id == excerpt_id, SourceExcerpt.source_id == source.id
        )
    )
    if not excerpt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Excerpt not found"},
        )
    await db.delete(excerpt)
    await db.commit()


@router.post("/suggest", response_model=ExcerptSuggestResponse)
@limiter.limit("10/hour")
async def suggest_source_excerpts(
    request: Request,
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_owned_source(source_id, current_user, db)
    try:
        await asyncio.to_thread(assert_url_is_safe, source.url)
    except UnsafeUrlError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "unsafe_url", "message": str(e)},
        ) from e

    # Import local : évite un cycle app.api ↔ app.extractors au démarrage.
    from app.extractors.url_extractor import _html_scrape

    meta = await _html_scrape(source.url)
    page_text = meta.page_text if meta else None
    if not page_text:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "no_text",
                "message": "Could not retrieve readable text from the source URL",
            },
        )

    context = " — ".join(filter(None, [source.title, source.annotation])) or None
    quotes = await suggest_excerpts(page_text, context)
    if quotes is None:
        return ExcerptSuggestResponse(
            suggestions=[], page_text_length=len(page_text), llm_enabled=False
        )

    suggestions: list[SuggestedExcerpt] = []
    seen: set[str] = set()
    for quote in quotes:
        m = verify_quote(page_text, quote)
        if not m:
            continue
        text = m.group(0)
        key = re.sub(r"\s+", " ", text).lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            SuggestedExcerpt(
                text=re.sub(r"\s+", " ", text),
                char_offset=m.start(),
                context_before=re.sub(r"\s+", " ", page_text[max(0, m.start() - 120) : m.start()]),
                context_after=re.sub(r"\s+", " ", page_text[m.end() : m.end() + 120]),
            )
        )
    return ExcerptSuggestResponse(
        suggestions=suggestions, page_text_length=len(page_text), llm_enabled=True
    )
