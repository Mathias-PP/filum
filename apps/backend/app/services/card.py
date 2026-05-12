from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.crypto.hashing import Canonicalizer, HashService, SigningService
from app.crypto.keygen import KeyManager
from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import ArchiveStatus, SourceType
from app.models.user import User
from app.schemas.biblio_card import CardCreate, CardStats

logger = logging.getLogger(__name__)
settings = get_settings()


class CardService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._key_manager = KeyManager(settings.master_encryption_key)

    async def create_card(self, user_id: UUID, card_data: CardCreate) -> BiblioCard:
        card = BiblioCard(
            user_id=user_id,
            slug=card_data.slug,
            title=card_data.title,
            description=card_data.description,
            content_url=card_data.content_url,
            platform=card_data.platform.value,
            content_type=card_data.content_type.value,
        )
        self._db.add(card)
        await self._db.commit()
        await self._db.refresh(card)
        return card

    async def get_card_by_id(self, card_id: UUID) -> BiblioCard | None:
        result = await self._db.execute(
            select(BiblioCard)
            .options(selectinload(BiblioCard.sources))
            .options(selectinload(BiblioCard.user))
            .where(BiblioCard.id == card_id)
        )
        return result.scalar_one_or_none()

    async def get_card_by_slug(
        self, user_slug: str, card_slug: str, published_only: bool = True
    ) -> BiblioCard | None:
        user_result = await self._db.execute(select(User).where(User.username == user_slug))
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        query = (
            select(BiblioCard)
            .options(selectinload(BiblioCard.sources))
            .options(selectinload(BiblioCard.user))
            .where(BiblioCard.user_id == user.id, BiblioCard.slug == card_slug)
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
        query = select(BiblioCard).where(BiblioCard.user_id == user_id)

        if status:
            query = query.where(BiblioCard.status == status)

        query = (
            query.options(selectinload(BiblioCard.sources))
            .order_by(BiblioCard.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def publish_card(self, card: BiblioCard) -> dict:
        sources_data = [
            {
                "url": s.url,
                "title": s.title,
                "source_type": s.source_type.value,
                "is_pivot": s.is_pivot,
                "archive_url": s.archive_url,
            }
            for s in sorted(card.sources, key=lambda x: x.position)
        ]

        content_to_sign = {
            "id": str(card.id),
            "title": card.title,
            "user_id": str(card.user_id),
            "slug": card.slug,
            "sources": sources_data,
            "created_at": card.created_at.isoformat(),
        }

        canonical = Canonicalizer.canonicalize(content_to_sign)
        content_hash = HashService.sha256(canonical)

        private_pem = self._key_manager.decrypt_private_key(card.user.encrypted_private_key)
        signer = SigningService.from_pem(private_pem)
        signature = signer.sign(content_hash)

        card.canonical_hash = content_hash
        card.signature = signature
        card.signed_at = datetime.now(UTC)
        card.published_at = datetime.now(UTC)
        card.status = CardStatus.PUBLISHED

        await self._db.commit()
        await self._db.refresh(card)

        return {
            "id": card.id,
            "status": card.status.value,
            "canonical_hash": content_hash,
            "signature": signature,
            "signed_at": card.signed_at,
            "published_at": card.published_at,
            "public_url": f"{settings.frontend_base_url}/@{card.user.username}/{card.slug}",
        }

    def compute_stats(self, card: BiblioCard) -> CardStats:
        sources = card.sources or []
        total = len(sources)
        peer_reviewed = sum(1 for s in sources if s.source_type == SourceType.PEER_REVIEWED)
        institutional = sum(1 for s in sources if s.source_type == SourceType.INSTITUTIONAL)
        press = sum(1 for s in sources if s.source_type == SourceType.PRESS)
        original = sum(1 for s in sources if s.source_type == SourceType.ORIGINAL)
        all_archived = all(s.archive_status == ArchiveStatus.ARCHIVED for s in sources)

        return CardStats(
            total_sources=total,
            peer_reviewed=peer_reviewed,
            institutional=institutional,
            press=press,
            original=original,
            all_archived=all_archived,
        )

    async def verify_card(self, card: BiblioCard) -> dict:
        sources_data = [
            {
                "url": s.url,
                "title": s.title,
                "source_type": s.source_type.value,
                "is_pivot": s.is_pivot,
                "archive_url": s.archive_url,
            }
            for s in sorted(card.sources, key=lambda x: x.position)
        ]

        content_to_sign = {
            "id": str(card.id),
            "title": card.title,
            "user_id": str(card.user_id),
            "slug": card.slug,
            "sources": sources_data,
            "created_at": card.created_at.isoformat(),
        }

        canonical = Canonicalizer.canonicalize(content_to_sign)
        content_hash = HashService.sha256(canonical)

        if content_hash != card.canonical_hash:
            return {"valid": False, "reason": "hash_mismatch"}

        try:
            signer = SigningService.from_pem(
                f"-----BEGIN PRIVATE KEY-----\n{card.user.public_key}\n-----END PRIVATE KEY-----"
            )
            if not signer.verify(content_hash, card.signature):
                return {"valid": False, "reason": "signature_mismatch"}
        except Exception as e:
            logger.warning(f"Verification failed: {e}")
            return {"valid": False, "reason": str(e)}

        return {
            "valid": True,
            "creator_slug": card.user.username,
            "card_slug": card.slug,
            "content_hash": content_hash,
            "signature": card.signature,
            "signed_at": card.signed_at,
            "details": {
                "hash_algorithm": "SHA-256",
                "signature_algorithm": "Ed25519",
                "canonicalization": "RFC 8785 JSON Canonicalization Scheme",
            },
        }
