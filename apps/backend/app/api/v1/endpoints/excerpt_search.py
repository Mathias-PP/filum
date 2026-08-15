"""Recherche d'extraits par le sens, sur ses propres fiches.

Route separee de `excerpts.py`, dont le routeur est prefixe par
`/sources/{source_id}` : la recherche ne porte pas sur une source mais sur tout
ce que la personne connectee a collecte.

La logique est dans `app.services.excerpt_search` ; ici on ne fait que
traduire son `None` en un etat que l'ecran sait afficher.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.sources import get_current_user
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.services.excerpt_search import rechercher

router = APIRouter(prefix="/excerpts", tags=["excerpts"])


class ExcerptSearchHit(BaseModel):
    excerpt_id: UUID
    text: str
    title: str | None
    context: str | None
    source_id: UUID
    source_title: str | None
    source_url: str
    card_id: UUID
    card_slug: str
    card_title: str
    # Cosinus entre la requete et l'extrait, de 0 a 1. Expose parce que
    # l'ecran doit pouvoir dire « de loin » : une liste ordonnee sans score
    # presente le dernier resultat avec le meme aplomb que le premier.
    similarity: float


class ExcerptSearchResponse(BaseModel):
    query: str
    results: list[ExcerptSearchHit]
    # Faux quand la recherche n'a pas pu avoir lieu : pas de service
    # d'embeddings, ou pgvector absent de la base. A ne pas confondre avec
    # `results: []`, qui veut dire que la recherche a eu lieu et n'a rien
    # trouve. L'ecran dit deux choses differentes, sans quoi une panne se
    # lirait comme un corpus muet.
    available: bool


@router.get("/search", response_model=ExcerptSearchResponse)
@limiter.limit("120/hour")
async def search_excerpts(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExcerptSearchResponse:
    """Les extraits de la personne connectee les plus proches de `q`."""
    resultats = await rechercher(db, current_user.id, q, limite=limit)
    if resultats is None:
        return ExcerptSearchResponse(query=q, results=[], available=False)
    return ExcerptSearchResponse(
        query=q,
        available=True,
        results=[
            ExcerptSearchHit(
                excerpt_id=r.excerpt_id,
                text=r.text,
                title=r.title,
                context=r.context,
                source_id=r.source_id,
                source_title=r.source_title,
                source_url=r.source_url,
                card_id=r.card_id,
                card_slug=r.card_slug,
                card_title=r.card_title,
                similarity=round(r.similarite, 4),
            )
            for r in resultats
        ],
    )
