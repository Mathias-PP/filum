"""Idempotent seed: creates a public demo card so /@example/filum-demo renders.

Run via `uv run python -m app.scripts.seed_demo`. Re-running is safe (no
duplicates). Invoked from the Dockerfile CMD after `alembic upgrade head`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.crypto.hashing import Canonicalizer, HashService, SigningService
from app.crypto.keygen import KeyManager
from app.db.database import async_session_maker
from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import ArchiveStatus, AuthorityLevel, Source, SourceType
from app.models.user import User

logger = logging.getLogger(__name__)

DEMO_USERNAME = "example"
DEMO_CARD_SLUG = "filum-demo"


async def _get_or_create_demo_user(db: AsyncSession, key_manager: KeyManager) -> User:
    result = await db.execute(select(User).where(User.username == DEMO_USERNAME))
    user = result.scalar_one_or_none()
    if user:
        return user

    private_pem, _public_pem, public_key_raw = KeyManager.generate_keypair()
    encrypted_private = key_manager.encrypt_private_key(private_pem)

    user = User(
        email="demo@filum.app",
        username=DEMO_USERNAME,
        display_name="Filum Demo",
        bio="Compte de démonstration. Fiche illustrant le format Filum.",
        public_key=public_key_raw,
        encrypted_private_key=encrypted_private,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _demo_sources() -> list[dict]:
    return [
        {
            "url": "https://www.nature.com/articles/s41586-020-2649-2",
            "title": "Array programming with NumPy",
            "authors": "Harris et al.",
            "source_type": SourceType.PEER_REVIEWED.value,
            "authority_level": AuthorityLevel.HIGH.value,
            "annotation": "Article de référence sur NumPy publié dans Nature en 2020.",
            "is_pivot": True,
        },
        {
            "url": "https://web.archive.org/web/2024/https://en.wikipedia.org/wiki/Citation",
            "title": "Citation — Wikipedia",
            "authors": "Wikipedia contributors",
            "source_type": SourceType.INSTITUTIONAL.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": "Définition encyclopédique du concept de citation.",
            "is_pivot": False,
        },
        {
            "url": "https://www.lemonde.fr/sciences/article/2024/01/01/exemple.html",
            "title": "Exemple d'article de presse",
            "authors": "Le Monde",
            "source_type": SourceType.PRESS.value,
            "authority_level": AuthorityLevel.MEDIUM.value,
            "annotation": "Article de presse généraliste à titre d'illustration.",
            "is_pivot": False,
        },
    ]


async def _get_or_create_demo_card(
    db: AsyncSession, user: User, key_manager: KeyManager
) -> BiblioCard:
    result = await db.execute(
        select(BiblioCard).where(
            BiblioCard.user_id == user.id,
            BiblioCard.slug == DEMO_CARD_SLUG,
        )
    )
    card = result.scalar_one_or_none()
    if card:
        return card

    card = BiblioCard(
        user_id=user.id,
        slug=DEMO_CARD_SLUG,
        title="Comment Filum signe une bibliographie",
        description=(
            "Fiche d'exemple présentant le format Filum : sources annotées, "
            "horodatage, signature Ed25519, archivage Wayback."
        ),
        content_url="https://example.org/filum-demo",
        platform=Platform.BLOG.value,
        content_type=ContentType.ARTICLE.value,
        status=CardStatus.DRAFT.value,
        canonical_hash="",
        signature="",
    )
    db.add(card)
    await db.flush()

    for position, src in enumerate(_demo_sources()):
        db.add(
            Source(
                biblio_card_id=card.id,
                position=position,
                url=src["url"],
                title=src["title"],
                authors=src["authors"],
                source_type=src["source_type"],
                authority_level=src["authority_level"],
                annotation=src["annotation"],
                is_pivot=src["is_pivot"],
                archive_status=ArchiveStatus.PENDING.value,
            )
        )

    await db.commit()
    await db.refresh(card, attribute_names=["sources", "user"])

    sources_data = [
        {
            "url": s.url,
            "title": s.title,
            "source_type": s.source_type,
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
    private_pem = key_manager.decrypt_private_key(card.user.encrypted_private_key)
    signature = SigningService.from_pem(private_pem).sign(content_hash)

    card.canonical_hash = content_hash
    card.signature = signature
    card.signed_at = datetime.utcnow()
    card.published_at = datetime.utcnow()
    card.status = CardStatus.PUBLISHED.value

    await db.commit()
    await db.refresh(card)
    return card


async def seed() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    settings = get_settings()
    key_manager = KeyManager(settings.master_encryption_key)

    async with async_session_maker() as db:
        user = await _get_or_create_demo_user(db, key_manager)
        card = await _get_or_create_demo_card(db, user, key_manager)
        logger.info(
            "Seed demo OK: user=%s card=%s status=%s",
            user.username,
            card.slug,
            card.status,
        )


if __name__ == "__main__":
    asyncio.run(seed())
