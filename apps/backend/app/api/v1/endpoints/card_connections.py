"""Gestion des connexions fiche a fiche par leur createur.

Une connexion est portee par une source (`Source.linked_card_id`). Elle peut
etre un geste du createur ou une hypothese de la machine, et le createur doit
pouvoir trancher. Voir les citations entrantes ne donne aucun droit dessus :
la bibliographie d'un autre createur lui appartient.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED

from app.db.database import get_db
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.schemas.card_connection import CardConnection, CardConnections
from app.services.auth import AuthService

router = APIRouter(tags=["connections"])


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def _get_current_user(
    request: Request, auth_service: AuthService = Depends(_get_auth_service)
) -> User:
    user = await auth_service.get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated"},
        )
    return user


async def _owned_card(db: AsyncSession, card_id: UUID, user: User) -> BiblioCard:
    card = await db.get(BiblioCard, card_id)
    if card is None or card.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fiche introuvable")
    if card.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette fiche ne vous appartient pas")
    return card


@router.get("/cards/{card_id}/connections", response_model=CardConnections)
async def list_connections(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_get_current_user),
) -> CardConnections:
    card = await _owned_card(db, card_id, user)

    outgoing_result = await db.execute(
        select(Source, BiblioCard, User)
        .join(BiblioCard, Source.linked_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            Source.biblio_card_id == card.id,
            Source.linked_card_id.is_not(None),
            Source.deleted_at.is_(None),
        )
        .order_by(Source.position)
    )
    incoming_result = await db.execute(
        select(Source, BiblioCard, User)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            Source.linked_card_id == card.id,
            Source.deleted_at.is_(None),
            BiblioCard.deleted_at.is_(None),
        )
        .order_by(Source.created_at)
    )

    def _row(src: Source, other: BiblioCard, creator: User, editable: bool) -> CardConnection:
        return CardConnection(
            source_id=src.id,
            source_title=src.title,
            source_url=src.url,
            card_id=other.id,
            card_title=other.title,
            card_slug=other.slug,
            card_creator_slug=creator.username,
            stance=src.stance,
            origin=src.link_origin,
            confirmed=src.link_confirmed_at is not None,
            # Une citation entrante appartient a la bibliographie d'un autre
            # createur : la voir n'autorise pas a la trancher.
            editable=editable,
        )

    return CardConnections(
        outgoing=[_row(s, c, u, True) for s, c, u in outgoing_result.all()],
        incoming=[_row(s, c, u, False) for s, c, u in incoming_result.all()],
    )


@router.post("/cards/{card_id}/connections/{source_id}/confirm", response_model=CardConnection)
async def confirm_connection(
    card_id: UUID,
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_get_current_user),
) -> CardConnection:
    card = await _owned_card(db, card_id, user)
    source = await db.get(Source, source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable")
    if source.biblio_card_id != card.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette source ne vous appartient pas")
    if source.linked_card_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette source ne designe aucune fiche")
    source.link_confirmed_at = _utcnow_naive()
    await db.flush()
    linked = await db.get(BiblioCard, source.linked_card_id)
    # Un `assert` disparait sous `python -O` : la ligne suivante levait alors
    # un AttributeError, donc un 500 muet, la ou la fiche designee a
    # simplement ete supprimee entre-temps. Le cas se dit, il ne s'affirme pas.
    if linked is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "La fiche designee n'existe plus")
    result = await db.execute(select(User).where(User.id == linked.user_id))
    creator = result.scalar_one()
    return CardConnection(
        source_id=source.id,
        source_title=source.title,
        source_url=source.url,
        card_id=linked.id,
        card_title=linked.title,
        card_slug=linked.slug,
        card_creator_slug=creator.username,
        stance=source.stance,
        origin=source.link_origin,
        confirmed=True,
        editable=True,
    )


@router.delete(
    "/cards/{card_id}/connections/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_connection(
    card_id: UUID,
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_get_current_user),
) -> None:
    card = await _owned_card(db, card_id, user)
    source = await db.get(Source, source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source introuvable")
    if source.biblio_card_id != card.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette source ne vous appartient pas")
    # Retirer le lien, pas la source : la reference reste dans la
    # bibliographie, elle cesse seulement de designer une fiche Philum.
    source.linked_card_id = None
    source.link_origin = None
    source.link_confirmed_at = None
    await db.flush()
