"""Annuaire public des fiches : une surface anonyme, humaine et machine.

Jusqu'ici on ne pouvait atteindre une fiche qu'en connaissant son adresse.
Tout etait deja public — le HTML est rendu cote serveur, le JSON-LD porte la
bibliographie complete — mais rien ne permettait de *trouver* une fiche. Cet
endpoint sert les deux publics d'un meme corps de requete : la page /discover
du site, et un agent conversationnel qui cherche de quoi etayer une reponse.
D'ou le champ `url` dans chaque resultat : de quoi citer sans second appel.

Aucune authentification, et donc un seul filtre qui vaille : publiee ET
publique. « Publiee » decrit l'avancement du travail, « publique » l'audience.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User

router = APIRouter(prefix="/discover", tags=["discover"])

_PUBLIC = (
    (BiblioCard.status == "published")
    & (BiblioCard.visibility == "public")
    & BiblioCard.deleted_at.is_(None)
)


class DiscoverResult(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    url: str
    creator_slug: str
    creator_name: str | None
    content_url: str | None
    content_authors: str | None
    content_type: str
    platform: str
    published_at: datetime | None
    source_count: int


class DiscoverResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[DiscoverResult]


class Facet(BaseModel):
    value: str
    count: int


class DiscoverFacets(BaseModel):
    total: int
    platforms: list[Facet]
    content_types: list[Facet]
    creators: list[Facet]


def _apply_filters(
    stmt: Select[Any],
    q: str,
    creator: str | None,
    content_author: str | None,
    platform: str | None,
    content_type: str | None,
    published_after: date | None,
    published_before: date | None,
) -> Select[Any]:
    """Les memes filtres pour les resultats et pour le decompte des facettes.

    Un seul chemin, sinon les compteurs de l'interface finissent par annoncer
    des options qui ne ramenent rien.
    """
    stmt = stmt.where(_PUBLIC)
    term = q.strip().lower()
    if term:
        # `autoescape` : sans lui, « % » et « _ » sont des jokers SQL et une
        # recherche sur « % » ramene tout le corpus.
        like = lambda col: func.lower(col).contains(term, autoescape=True)  # noqa: E731
        stmt = stmt.where(
            or_(
                like(BiblioCard.title),
                like(BiblioCard.description),
                like(BiblioCard.content_authors),
                like(User.username),
                like(User.display_name),
            )
        )
    if creator:
        stmt = stmt.where(func.lower(User.username) == creator.strip().lower())
    if content_author:
        stmt = stmt.where(
            func.lower(BiblioCard.content_authors).contains(
                content_author.strip().lower(), autoescape=True
            )
        )
    if platform:
        stmt = stmt.where(BiblioCard.platform == platform)
    if content_type:
        stmt = stmt.where(BiblioCard.content_type == content_type)
    if published_after:
        stmt = stmt.where(
            BiblioCard.published_at >= datetime.combine(published_after, datetime.min.time())
        )
    if published_before:
        stmt = stmt.where(
            BiblioCard.published_at <= datetime.combine(published_before, datetime.max.time())
        )
    return stmt


@router.get("", response_model=DiscoverResponse)
async def discover_cards(
    q: str = Query("", max_length=200),
    creator: str | None = Query(None, max_length=100),
    content_author: str | None = Query(None, max_length=200),
    platform: str | None = Query(None, max_length=50),
    content_type: str | None = Query(None, max_length=50),
    published_after: date | None = Query(None),
    published_before: date | None = Query(None),
    sort: str = Query("recent", pattern="^(recent|sources|title)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DiscoverResponse:
    args = (q, creator, content_author, platform, content_type, published_after, published_before)

    source_count = (
        select(func.count(Source.id))
        .where(Source.biblio_card_id == BiblioCard.id, Source.deleted_at.is_(None))
        .correlate(BiblioCard)
        .scalar_subquery()
    )

    base = select(BiblioCard, User.username, User.display_name, source_count.label("n")).join(
        User, User.id == BiblioCard.user_id
    )
    stmt = _apply_filters(base, *args)

    if sort == "sources":
        stmt = stmt.order_by(source_count.desc(), BiblioCard.published_at.desc().nullslast())
    elif sort == "title":
        stmt = stmt.order_by(func.lower(BiblioCard.title))
    else:
        stmt = stmt.order_by(
            BiblioCard.published_at.desc().nullslast(), BiblioCard.created_at.desc()
        )

    count_stmt = _apply_filters(
        select(func.count(BiblioCard.id)).join(User, User.id == BiblioCard.user_id), *args
    )
    total = (await db.scalar(count_stmt)) or 0

    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()
    base_url = get_settings().frontend_base_url.rstrip("/")
    return DiscoverResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=[
            DiscoverResult(
                id=str(card.id),
                slug=card.slug,
                title=card.title,
                description=card.description,
                url=f"{base_url}/@{username}/{card.slug}",
                creator_slug=username,
                creator_name=display_name,
                content_url=card.content_url,
                content_authors=card.content_authors,
                content_type=card.content_type,
                platform=card.platform,
                published_at=card.published_at,
                source_count=n,
            )
            for card, username, display_name, n in rows
        ],
    )


class CreatorResult(BaseModel):
    slug: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    is_verified: bool
    published_cards_count: int
    url: str


class CreatorSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[CreatorResult]


@router.get("/creators", response_model=CreatorSearchResponse)
async def discover_creators(
    q: str = Query("", max_length=200),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CreatorSearchResponse:
    """Recherche de createurs qui ont au moins une fiche publique publiee.

    Indexe uniquement ce que le createur a rendu public : `username`,
    `display_name`, `bio`. Ne remonte jamais un compte qui n'a publie
    aucune fiche : sans corpus, un profil n'a rien a offrir a la recherche.
    """
    published_count = (
        select(func.count(BiblioCard.id))
        .where(BiblioCard.user_id == User.id, _PUBLIC)
        .correlate(User)
        .scalar_subquery()
    )
    base = select(User, published_count.label("n")).where(published_count > 0)

    term = q.strip().lower()
    if term:
        like = lambda col: func.lower(col).contains(term, autoescape=True)  # noqa: E731
        base = base.where(
            or_(like(User.username), like(User.display_name), like(User.bio))
        )

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.scalar(total_stmt)) or 0

    rows = (
        await db.execute(
            base.order_by(published_count.desc(), func.lower(User.username))
            .limit(limit)
            .offset(offset)
        )
    ).all()

    base_url = get_settings().frontend_base_url.rstrip("/")
    return CreatorSearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=[
            CreatorResult(
                slug=user.username,
                display_name=user.display_name,
                bio=user.bio,
                avatar_url=user.avatar_url,
                is_verified=user.is_verified,
                published_cards_count=n,
                url=f"{base_url}/@{user.username}",
            )
            for user, n in rows
        ],
    )


@router.get("/facets", response_model=DiscoverFacets)
async def discover_facets(db: AsyncSession = Depends(get_db)) -> DiscoverFacets:
    """Ce qui existe reellement dans le corpus public.

    L'interface n'invente pas ses filtres a partir des enums du modele : une
    case a cocher qui ne ramene jamais rien est une promesse non tenue.
    """

    async def counts(column: Any) -> list[Facet]:
        stmt = (
            select(column, func.count(BiblioCard.id))
            .join(User, User.id == BiblioCard.user_id)
            .where(_PUBLIC, column.is_not(None))
            .group_by(column)
            .order_by(func.count(BiblioCard.id).desc())
        )
        return [Facet(value=str(v), count=c) for v, c in (await db.execute(stmt)).all()]

    total = (
        await db.scalar(
            select(func.count(BiblioCard.id))
            .join(User, User.id == BiblioCard.user_id)
            .where(_PUBLIC)
        )
    ) or 0
    return DiscoverFacets(
        total=total,
        platforms=await counts(BiblioCard.platform),
        content_types=await counts(BiblioCard.content_type),
        creators=await counts(User.username),
    )
