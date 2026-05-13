"""Tests for the canonical_hash invariance of published BiblioCards.

The canonical_hash payload is FROZEN by design (cf. CLAUDE.md, AGENTS.md,
agent/PITFALLS.md 1.3, ADR-016, ADR-017). Any change to the set of fields
that enter the payload silently invalidates the Ed25519 signature of every
previously-signed card.

These tests pin the invariance contract by:
  1. Publishing a card (computes canonical_hash + signature)
  2. Mutating a field that MUST be outside the payload
  3. Re-publishing
  4. Asserting the canonical_hash is unchanged

And, symmetrically, that mutating an in-payload field DOES change the hash.

Reference: apps/backend/app/services/card.py lines 96-105 and 165-184.
"""

from __future__ import annotations

from uuid import uuid4

import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.biblio_card import BiblioCard
from app.models.source import ArchiveStatus, Source, SourceType
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.services.card import CardService


@pytest_asyncio.fixture
async def real_keyed_user(db_session):
    """A user with a real Ed25519 keypair, encrypted with the test master key."""
    settings = get_settings()
    key_manager = KeyManager(settings.master_encryption_key)
    private_pem, _public_pem, public_key_raw = KeyManager.generate_keypair()
    encrypted_private = key_manager.encrypt_private_key(private_pem)

    user = User(
        id=uuid4(),
        email="hashtest@example.com",
        username="hashtester",
        display_name="Hash Tester",
        public_key=public_key_raw,
        encrypted_private_key=encrypted_private,
        google_id="hashtest_google_id",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def published_card(db_session, real_keyed_user):
    """A BiblioCard with 2 sources, published and signed."""
    # NOTE: BiblioCard.canonical_hash and .signature are declared
    # `nullable=False` in the SQLAlchemy model, but the production
    # CardService.create_card() method does NOT set them on draft cards.
    # This works against Postgres (where a migration loosened the constraint)
    # but fails against SQLite tables built from Base.metadata.create_all,
    # which faithfully follows the model declaration.
    # See PR description "Discovered gaps" — model/migration drift.
    # We pass empty strings here so publish_card() can overwrite them.
    card = BiblioCard(
        id=uuid4(),
        user_id=real_keyed_user.id,
        slug="invariance-demo",
        title="Invariance demo card",
        description="Tests that the payload is frozen.",
        content_url="https://example.com/video",
        platform="youtube",
        content_type="video",
        canonical_hash="",
        signature="",
    )
    db_session.add(card)
    await db_session.flush()

    src1 = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        url="https://nature.com/a",
        title="A",
        source_type=SourceType.PEER_REVIEWED,
        is_pivot=True,
        archive_url="https://web.archive.org/A",
        position=0,
        archive_status=ArchiveStatus.ARCHIVED,
    )
    src2 = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        url="https://news.example/b",
        title="B",
        source_type=SourceType.PRESS,
        is_pivot=False,
        archive_url="https://web.archive.org/B",
        position=1,
        archive_status=ArchiveStatus.ARCHIVED,
    )
    db_session.add_all([src1, src2])
    await db_session.commit()

    service = CardService(db_session)
    fresh = await service.get_card_by_id(card.id)
    assert fresh is not None
    await service.publish_card(fresh)

    refreshed = await service.get_card_by_id(card.id)
    assert refreshed is not None
    assert refreshed.canonical_hash is not None
    assert refreshed.signature is not None
    return refreshed


# ---------------------------------------------------------------------------
# Fields OUTSIDE the canonical_hash payload — mutation must NOT change the hash.
# ---------------------------------------------------------------------------


async def test_hash_invariant_under_source_excerpt_added(db_session, published_card):
    """Adding a SourceExcerpt must not change canonical_hash."""
    original_hash = published_card.canonical_hash
    src = published_card.sources[0]

    excerpt = SourceExcerpt(
        id=uuid4(),
        source_id=src.id,
        position=0,
        text="A relevant quote that should not affect the hash.",
        suggested_by_ai=False,
    )
    db_session.add(excerpt)
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash == original_hash


async def test_hash_invariant_under_parent_source_id_change(db_session, published_card):
    """parent_source_id is a structural/visual link, NOT in the signed payload."""
    original_hash = published_card.canonical_hash
    src1, src2 = published_card.sources[0], published_card.sources[1]

    src2.parent_source_id = src1.id
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash == original_hash


async def test_hash_invariant_under_iteration_2_fields(db_session, published_card):
    """citations_count, conflict_of_interest, impact_factor: all out of payload."""
    original_hash = published_card.canonical_hash
    src = published_card.sources[0]

    src.citations_count = 9999
    src.conflict_of_interest = "Author funded by X"
    src.impact_factor = 12.3
    src.subscribers_count = 100_000
    src.views_count = 1_000_000
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash == original_hash


async def test_hash_invariant_under_description_change(db_session, published_card):
    """card.description is not in the signed payload."""
    original_hash = published_card.canonical_hash
    published_card.description = "Completely rewritten description."
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash == original_hash


async def test_hash_invariant_under_authors_and_annotation_change(db_session, published_card):
    """source.authors, source.annotation: editorial fields, out of payload."""
    original_hash = published_card.canonical_hash
    src = published_card.sources[0]
    src.authors = "Newly added author"
    src.annotation = "Newly added annotation explaining why this matters."
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash == original_hash


# ---------------------------------------------------------------------------
# Fields INSIDE the canonical_hash payload — mutation MUST change the hash.
# ---------------------------------------------------------------------------


async def test_hash_changes_when_card_title_changes(db_session, published_card):
    original_hash = published_card.canonical_hash
    published_card.title = "Renamed card title"
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash != original_hash


async def test_hash_changes_when_source_url_changes(db_session, published_card):
    original_hash = published_card.canonical_hash
    published_card.sources[0].url = "https://nature.com/a-revised"
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash != original_hash


async def test_hash_changes_when_source_is_pivot_toggles(db_session, published_card):
    """is_pivot IS in the payload — toggling it must produce a different hash."""
    original_hash = published_card.canonical_hash
    published_card.sources[1].is_pivot = True
    await db_session.commit()

    service = CardService(db_session)
    refreshed = await service.get_card_by_id(published_card.id)
    assert refreshed is not None
    await service.publish_card(refreshed)
    assert refreshed.canonical_hash != original_hash


# ---------------------------------------------------------------------------
# Sanity: signature is genuine Ed25519 on the canonical_hash.
# ---------------------------------------------------------------------------


async def test_signature_is_valid_ed25519_on_canonical_hash(db_session, published_card):
    """Decode the user's public key and verify the signature against the hash."""
    settings = get_settings()
    key_manager = KeyManager(settings.master_encryption_key)
    private_pem = key_manager.decrypt_private_key(published_card.user.encrypted_private_key)
    priv = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
    assert isinstance(priv, ed25519.Ed25519PrivateKey)
    pub = priv.public_key()

    signature_bytes = bytes.fromhex(published_card.signature)
    # The service signs the *hex string* of the hash, not the raw bytes.
    pub.verify(signature_bytes, published_card.canonical_hash.encode("utf-8"))
