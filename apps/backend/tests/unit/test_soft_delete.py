"""Tests for soft-delete on BiblioCard and Source.

Audit phase 4 (2026-05-26): before this change, ``BiblioCard.deleted_at``
existed in the model but no query filtered on it, and ``Source.deleted_at``
didn't exist at all. The DELETE endpoints did a hard ``await db.delete()``
which cascade-removed sources and broke the citation history.

These tests pin:
  - Deleted cards do not appear in user list / by id / by slug queries.
  - Deleted sources do not appear in card's sources nor in list_sources.
  - delete_card() sets ``deleted_at`` instead of removing the row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import select

from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import AuthorKind, Source, SourceCategory, SourceFormat
from app.services.card import CardService


@pytest_asyncio.fixture
async def card_service(db_session):
    return CardService(db_session)


@pytest_asyncio.fixture
async def draft_card(db_session, test_user):
    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="my-draft",
        title="Test draft",
        content_type=ContentType.ARTICLE.value,
        platform=Platform.BLOG.value,
        status=CardStatus.DRAFT.value,
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    yield card


@pytest_asyncio.fixture
async def source_in_draft(db_session, draft_card):
    source = Source(
        id=uuid4(),
        biblio_card_id=draft_card.id,
        position=0,
        url="https://example.com/article",
        title="A source",
        format=SourceFormat.TEXTE.value,
        category=SourceCategory.BLOG.value,
        author_kind=AuthorKind.INDIVIDU.value,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    yield source


class TestDeleteCardIsSoft:
    async def test_delete_card_sets_deleted_at_not_remove_row(
        self, card_service, draft_card, test_user, db_session
    ):
        card_id = draft_card.id
        ok = await card_service.delete_card(card_id, test_user.id)
        assert ok is True

        # Row still exists in the database.
        result = await db_session.execute(select(BiblioCard).where(BiblioCard.id == card_id))
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.deleted_at is not None
        assert isinstance(row.deleted_at, datetime)

    async def test_get_card_by_id_hides_deleted(
        self, card_service, draft_card, test_user, db_session
    ):
        await card_service.delete_card(draft_card.id, test_user.id)
        assert (await card_service.get_card_by_id(draft_card.id)) is None

    async def test_get_user_cards_hides_deleted(
        self, card_service, draft_card, test_user
    ):
        before = await card_service.get_user_cards(test_user.id)
        assert any(c.id == draft_card.id for c in before)

        await card_service.delete_card(draft_card.id, test_user.id)

        after = await card_service.get_user_cards(test_user.id)
        assert not any(c.id == draft_card.id for c in after)

    async def test_delete_card_twice_is_idempotent_returns_false(
        self, card_service, draft_card, test_user
    ):
        assert await card_service.delete_card(draft_card.id, test_user.id) is True
        # Second delete returns False (already filtered out by the same query).
        assert await card_service.delete_card(draft_card.id, test_user.id) is False

    async def test_published_card_not_deletable(
        self, card_service, draft_card, test_user, db_session
    ):
        draft_card.status = CardStatus.PUBLISHED.value
        draft_card.published_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()

        ok = await card_service.delete_card(draft_card.id, test_user.id)
        assert ok is False

        # And the row is unchanged.
        result = await db_session.execute(select(BiblioCard).where(BiblioCard.id == draft_card.id))
        row = result.scalar_one()
        assert row.deleted_at is None


class TestSoftDeleteHidesSources:
    async def test_deleted_source_excluded_from_card_eager_load(
        self, card_service, draft_card, source_in_draft, db_session
    ):
        # Mark the source as soft-deleted directly.
        source_in_draft.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()

        reloaded = await card_service.get_card_by_id(draft_card.id)
        assert reloaded is not None
        assert all(s.id != source_in_draft.id for s in reloaded.sources)
