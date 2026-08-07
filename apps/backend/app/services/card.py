from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import ArchiveStatus, AuthorKind, Source
from app.models.user import User
from app.schemas.biblio_card import CardCreate, CardStats
from app.services.card_link import link_sources_designating_card

settings = get_settings()


class CardService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_card(self, user_id: UUID, card_data: CardCreate) -> BiblioCard:
        card = BiblioCard(
            user_id=user_id,
            slug=card_data.slug,
            title=card_data.title,
            description=card_data.description,
            content_url=card_data.content_url,
            content_authors=card_data.content_authors,
            platform=card_data.platform.value,
            content_type=card_data.content_type.value,
            is_seed=card_data.is_seed,
            visibility=card_data.visibility.value,
        )
        self._db.add(card)
        await self._db.commit()
        await self._db.refresh(card)
        return card

    async def get_card_by_id(self, card_id: UUID) -> BiblioCard | None:
        result = await self._db.execute(
            select(BiblioCard)
            # Hide soft-deleted sources from the eager-load. The card's
            # `deleted_at IS NULL` filter is on the outer query below.
            .options(
                selectinload(BiblioCard.sources.and_(Source.deleted_at.is_(None))).selectinload(
                    Source.excerpts
                )
            )
            .options(selectinload(BiblioCard.user))
            .where(BiblioCard.id == card_id, BiblioCard.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_card_by_slug(
        self, user_slug: str, card_slug: str, published_only: bool = True
    ) -> BiblioCard | None:
        query = (
            select(BiblioCard)
            .join(User, BiblioCard.user_id == User.id)
            .options(
                selectinload(BiblioCard.sources.and_(Source.deleted_at.is_(None))).selectinload(
                    Source.excerpts
                )
            )
            .options(selectinload(BiblioCard.user))
            .where(
                User.username == user_slug,
                BiblioCard.slug == card_slug,
                BiblioCard.deleted_at.is_(None),
            )
        )

        if published_only:
            query = query.where(BiblioCard.status == CardStatus.PUBLISHED)

        result = await self._db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_cards(
        self,
        user_id: UUID,
        status: CardStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[BiblioCard]:
        query = select(BiblioCard).where(
            BiblioCard.user_id == user_id, BiblioCard.deleted_at.is_(None)
        )

        if status:
            query = query.where(BiblioCard.status == status)

        query = (
            query.options(
                selectinload(BiblioCard.sources.and_(Source.deleted_at.is_(None))).selectinload(
                    Source.excerpts
                )
            )
            .order_by(BiblioCard.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def save_card(self, card: BiblioCard) -> BiblioCard:
        """Commit pending mutations on a card already attached to this session."""
        await self._db.commit()
        await self._db.refresh(card)
        return card

    async def get_user_deleted_cards(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[BiblioCard]:
        """Renvoie les fiches soft-deletees de l'utilisateur (corbeille).

        Utile pour la vue Corbeille dans le dashboard : l'user peut restaurer
        une fiche supprimee tant qu'elle n'a pas ete purgee. Ordre = plus
        recemment supprimee en premier.
        """
        result = await self._db.execute(
            select(BiblioCard)
            .where(
                BiblioCard.user_id == user_id,
                BiblioCard.deleted_at.is_not(None),
            )
            .order_by(BiblioCard.deleted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def publish_card(self, card: BiblioCard) -> dict:
        # Capture scalar values from relations BEFORE commit.
        # Post-commit, SQLAlchemy expires loaded relations; accessing card.user
        # then triggers a lazy-load outside the greenlet context → MissingGreenlet.
        username = card.user.username
        card_slug = card.slug

        now = datetime.now(UTC).replace(tzinfo=None)
        was_already_published = card.status == CardStatus.PUBLISHED
        card.published_at = now
        card.status = CardStatus.PUBLISHED

        # La fiche vient d'exister publiquement : les references deja saisies
        # ailleurs vers le meme contenu la designent desormais. Sans ce
        # rattrapage elles resteraient isolees sur le meta-graphe.
        await link_sources_designating_card(self._db, card)

        # Registre chronologique (voir .docs/20-profils-et-feed.md) : une
        # entree par publication effective d'une fiche publique. Republier
        # une fiche deja publiee n'en cree pas une seconde — le feed est un
        # horodatage du premier passage au public, pas un journal d'edition.
        # Les fiches privees n'entrent jamais dans le feed.
        if not was_already_published and card.visibility == "public":
            from app.models.feed_event import FeedEvent, FeedEventKind

            self._db.add(
                FeedEvent(
                    kind=FeedEventKind.CARD_PUBLISHED,
                    actor_id=card.user_id,
                    card_id=card.id,
                    occurred_at=now,
                )
            )

        await self._db.commit()

        return {
            "id": card.id,
            "status": card.status,
            "published_at": card.published_at,
            "public_url": f"{settings.frontend_base_url}/@{username}/{card_slug}",
        }

    def compute_stats(self, card: BiblioCard) -> CardStats:
        sources = card.sources or []
        total = len(sources)
        chercheur = sum(1 for s in sources if s.author_kind == AuthorKind.CHERCHEUR.value)
        media = sum(1 for s in sources if s.author_kind == AuthorKind.MEDIA.value)
        institution_publique = sum(
            1 for s in sources if s.author_kind == AuthorKind.INSTITUTION_PUBLIQUE.value
        )
        individu = sum(1 for s in sources if s.author_kind == AuthorKind.INDIVIDU.value)
        archived_count = sum(1 for s in sources if s.archive_status == ArchiveStatus.ARCHIVED.value)
        # Une source sans URL n'a rien a archiver. La compter au denominateur
        # condamnerait une fiche pourtant complete a afficher « 148/152 » a
        # perpetuite, et « tout archive » a ne jamais s'allumer.
        archivable_count = sum(
            1 for s in sources if s.archive_status != ArchiveStatus.NOT_APPLICABLE.value
        )
        all_archived = archivable_count > 0 and archived_count == archivable_count

        return CardStats(
            total_sources=total,
            chercheur=chercheur,
            media=media,
            institution_publique=institution_publique,
            individu=individu,
            archived_count=archived_count,
            archivable_count=archivable_count,
            all_archived=all_archived,
        )

    async def delete_card(self, card_id: UUID, user_id: UUID) -> bool:
        """Soft-delete a card (draft OR published) owned by ``user_id``.

        Sets ``deleted_at`` to now instead of removing the row. The card's
        sources stay in the DB (they're referenced by content_attestations
        and any incoming citation graph from other cards); they just become
        invisible because every public query filters
        ``BiblioCard.deleted_at IS NULL``.

        Note (ADR-019 revisitee, 2026-07-20) : les fiches publiees sont
        aussi soft-deletable par leur owner. La *fiche* (page publique
        agregee) est la vue produit ; l'engagement public est porte par
        l'*attestation Ed25519* (content_attestations), qui reste en base
        et verifiable via son id. Soft-delete de la fiche != revocation
        de l'attestation. Annulable via ``restore_card``.
        """
        result = await self._db.execute(
            select(BiblioCard).where(
                BiblioCard.id == card_id,
                BiblioCard.user_id == user_id,
                BiblioCard.deleted_at.is_(None),
            )
        )
        card = result.scalar_one_or_none()
        if not card:
            return False
        card.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self._db.commit()
        return True

    async def restore_card(self, card_id: UUID, user_id: UUID) -> BiblioCard | None:
        """Annule un soft-delete : remet ``deleted_at`` a NULL."""
        result = await self._db.execute(
            select(BiblioCard).where(
                BiblioCard.id == card_id,
                BiblioCard.user_id == user_id,
                BiblioCard.deleted_at.is_not(None),
            )
        )
        card = result.scalar_one_or_none()
        if not card:
            return None
        card.deleted_at = None
        await self._db.commit()
        await self._db.refresh(card)
        return card
