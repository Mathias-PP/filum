"""Extraits (citations) d'une source : CRUD + suggestion IA.

La suggestion IA repère des citations *verbatim* dans le texte de la source
(alias LiteLLM `excerpt-suggest`). Anti-hallucination : chaque extrait
proposé est vérifié par recherche exacte (espaces normalisés) dans le texte
récupéré — un extrait introuvable est écarté, jamais exposé.

L'emplacement (voisinage + offset) est **persisté** depuis #333 : sans lui, un
extrait ne se retrouvait qu'au mot près et devenait introuvable dès que la page
corrigeait une coquille. `/verify` s'en sert pour ré-ancrer les extraits dans la
page telle qu'elle est aujourd'hui — cf. `app/services/excerpt_anchor.py`.
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
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.schemas.source import SourceExcerptResponse
from app.services.chunker import Unite, chunk_text, compter, suggerer_taille
from app.services.excerpt_anchor import Selecteurs, ancrer
from app.services.llm import suggest_chunk_titles, suggest_excerpts

router = APIRouter(prefix="/sources/{source_id}/excerpts", tags=["excerpts"])

MAX_EXCERPTS_PER_SOURCE = 10


class ExcerptCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=200)
    suggested_by_ai: bool = False
    # Voisinage et position du passage dans le texte d'ou il vient. Facultatifs :
    # un extrait saisi a la main, sans que le texte de la source soit connu, n'en
    # a pas — et l'ecran doit alors le dire plutot que de faire semblant.
    anchor_prefix: str | None = Field(default=None, max_length=500)
    anchor_suffix: str | None = Field(default=None, max_length=500)
    anchor_offset: int | None = Field(default=None, ge=0)


# --- Decoupage : le texte colle, quand le site ne se laisse pas lire --------
#
# Mesure du 2026-08-08 sur dix URLs, dont les quatre personas de l'audit :
# cinq ne rendent aucun texte exploitable -- NYT, ScienceDirect, treasury.gov
# et Cell rendent zero caractere, YouTube 313. `/suggest` y repondait
# `422 no_text` : la fonctionnalite s'arretait a la porte alors que la personne
# a le texte sous les yeux.
#
# D'ou ce second chemin, qui accepte le texte colle et ne depend d'aucun fetch.
# Une page illisible n'y est pas une erreur mais un etat declare (`text_source`)
# sur lequel l'interface bascule.

# Un collage tient un long chapitre ; au-dela on refuse plutot que de tronquer
# en silence, une troncature invisible faisant citer un texte que l'auteur·ice
# croit avoir fourni en entier.
MAX_PASTED_CHARS = 200_000


class ChunkRequest(BaseModel):
    text: str | None = Field(default=None, max_length=MAX_PASTED_CHARS)
    unit: Unite = Unite.CARACTERES
    size: int | None = Field(default=None, ge=1)
    # La suggestion d'intitules coute un appel LLM : elle se demande.
    suggest_titles: bool = False


class ChunkOut(BaseModel):
    text: str
    start: int
    end: int
    size: int
    title: str | None = None


class ChunkResponse(BaseModel):
    chunks: list[ChunkOut]
    text: str
    text_source: str  # "pasted" | "fetched" | "none"
    unit: Unite
    suggested_size: int
    # Mesure du 2026-08-08 : la prod ne definit aucune variable LiteLLM, donc
    # la suggestion d'intitules n'y rend rien. Une case a cocher qui promet un
    # service absent est du meme genre qu'un titre faux — elle se lit comme une
    # offre. L'ecran a besoin de le savoir pour le dire.
    llm_enabled: bool


def decouper_pour_reponse(texte: str, payload: ChunkRequest) -> ChunkResponse:
    """Decoupe `texte` et decrit le resultat, sans jamais lever.

    `payload.text` ne sert qu'a dire d'ou vient le texte : l'appelant a deja
    tranche entre le collage et la recuperation.
    """
    provenance = "pasted" if payload.text else ("fetched" if texte.strip() else "none")
    suggeree = suggerer_taille(texte, payload.unit)
    taille = payload.size or suggeree
    chunks = chunk_text(texte, taille=taille, unite=payload.unit)
    return ChunkResponse(
        chunks=[
            ChunkOut(text=c.text, start=c.start, end=c.end, size=compter(c.text, payload.unit))
            for c in chunks
        ],
        text=texte,
        text_source=provenance,
        unit=payload.unit,
        suggested_size=suggeree,
        llm_enabled=bool(get_settings().litellm_base_url),
    )


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
        title=(payload.title or "").strip() or None,
        suggested_by_ai=payload.suggested_by_ai,
        anchor_prefix=payload.anchor_prefix,
        anchor_suffix=payload.anchor_suffix,
        anchor_offset=payload.anchor_offset,
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


@router.post("/chunk", response_model=ChunkResponse)
@limiter.limit("60/hour")
async def chunk_source_text(
    request: Request,
    source_id: UUID,
    payload: ChunkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Propose un decoupage du texte de la source, colle ou recupere.

    Le collage prime : c'est le seul chemin qui marche sur les cinq sites de la
    mesure ou la recuperation ne rend rien. Sans collage on tente le site, et
    une page illisible rend un decoupage vide plutot qu'une erreur.
    """
    source = await _get_owned_source(source_id, current_user, db)

    texte = (payload.text or "").strip()
    if not texte:
        try:
            await asyncio.to_thread(assert_url_is_safe, source.url)
        except UnsafeUrlError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "unsafe_url", "message": str(e)},
            ) from e
        from app.extractors.url_extractor import _html_scrape

        meta = await _html_scrape(source.url)
        texte = (meta.page_text if meta else None) or ""

    reponse = decouper_pour_reponse(texte, payload)
    if payload.suggest_titles and reponse.chunks:
        titres = await suggest_chunk_titles([c.text for c in reponse.chunks])
        if titres:
            for chunk, titre in zip(reponse.chunks, titres, strict=False):
                chunk.title = titre
    return reponse


class ExcerptCheck(BaseModel):
    excerpt_id: UUID
    #: `found` : le passage est dans la page. `moved` : il y est, mais plus tout
    #: a fait dans ces mots. `missing` : il n'y est pas. `unreadable` : la page
    #: n'a pas rendu de texte — **on ne sait pas**, ce qui n'est pas la meme
    #: chose que « absent ». Confondre les deux ferait passer une source
    #: inaccessible pour une citation inventee.
    status: str
    start: int | None = None
    end: int | None = None
    context_before: str | None = None
    context_after: str | None = None


class ExcerptVerifyResponse(BaseModel):
    checks: list[ExcerptCheck]
    page_text_length: int


@router.post("/verify", response_model=ExcerptVerifyResponse)
@limiter.limit("20/hour")
async def verify_source_excerpts(
    request: Request,
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reancre chaque extrait dans la page telle qu'elle est aujourd'hui.

    C'est ce qui fait passer un extrait de *declare* a *verifie* : sans cette
    passe, la fiche affirme qu'une source dit quelque chose sans que rien ne
    l'ait jamais confirme.
    """
    source = await _get_owned_source(source_id, current_user, db)
    excerpts = list(
        (
            await db.scalars(
                select(SourceExcerpt)
                .where(SourceExcerpt.source_id == source.id)
                .order_by(SourceExcerpt.position)
            )
        ).all()
    )
    if not excerpts:
        return ExcerptVerifyResponse(checks=[], page_text_length=0)

    try:
        await asyncio.to_thread(assert_url_is_safe, source.url)
    except UnsafeUrlError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "unsafe_url", "message": str(e)},
        ) from e

    from app.extractors.url_extractor import _html_scrape

    meta = await _html_scrape(source.url)
    page_text = (meta.page_text if meta else None) or ""
    if not page_text.strip():
        # Cinq URLs sur dix ne rendent aucun texte (mesure du 2026-08-08). Dire
        # « introuvable » ici accuserait l'auteur·ice a la place du site.
        return ExcerptVerifyResponse(
            checks=[ExcerptCheck(excerpt_id=x.id, status="unreadable") for x in excerpts],
            page_text_length=0,
        )

    checks: list[ExcerptCheck] = []
    for extrait in excerpts:
        ancrage = ancrer(
            page_text,
            Selecteurs(
                quote=extrait.text,
                prefix=extrait.anchor_prefix or "",
                suffix=extrait.anchor_suffix or "",
                offset=extrait.anchor_offset,
            ),
        )
        if ancrage is None:
            checks.append(ExcerptCheck(excerpt_id=extrait.id, status="missing"))
            continue
        checks.append(
            ExcerptCheck(
                excerpt_id=extrait.id,
                status="found" if ancrage.exact else "moved",
                start=ancrage.start,
                end=ancrage.end,
                context_before=re.sub(
                    r"\s+", " ", page_text[max(0, ancrage.start - 120) : ancrage.start]
                ),
                context_after=re.sub(r"\s+", " ", page_text[ancrage.end : ancrage.end + 120]),
            )
        )
    return ExcerptVerifyResponse(checks=checks, page_text_length=len(page_text))


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
        # Cinq URLs sur dix ne rendent rien (mesure du 2026-08-08). Ce n'est
        # pas un echec de l'appel : c'est l'etat qui fait basculer l'interface
        # sur le collage. Un `422` y coupait court.
        #
        # `llm_enabled` dit ici l'etat reel du serveur et non un `True` de
        # commodite : sans modele configure — cas de la prod, mesure le
        # 2026-08-08 — l'ecran afficherait « aucun passage citable repere »
        # pour une absence de modele, en donnant la mauvaise cause a lire.
        return ExcerptSuggestResponse(
            suggestions=[],
            page_text_length=0,
            llm_enabled=bool(get_settings().litellm_base_url),
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
