from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.user import SlugPattern
from app.schemas.biblio_card import CardCreate, Platform, ContentType
from app.schemas.source import SourceCreate, SourceType, SourceUpdate


class TestUserSchemas:
    def test_valid_slug(self):
        assert SlugPattern.match("lea-c")
        assert SlugPattern.match("test123")
        assert SlugPattern.match("a123")

    def test_invalid_slug_too_short(self):
        assert not SlugPattern.match("ab")
        assert not SlugPattern.match("a")

    def test_invalid_slug_uppercase(self):
        assert not SlugPattern.match("LeaC")
        assert not SlugPattern.match("LEA-C")

    def test_invalid_slug_special_chars(self):
        assert not SlugPattern.match("lea_c")
        assert not SlugPattern.match("lea.c")


class TestCardSchemas:
    def test_valid_card_create(self):
        data = CardCreate(
            slug="test-video-2026",
            title="Test Video Title",
            platform=Platform.YOUTUBE,
            content_type=ContentType.VIDEO,
        )
        assert data.slug == "test-video-2026"
        assert data.platform == Platform.YOUTUBE

    def test_slug_pattern_must_match(self):
        assert not SlugPattern.match("ab")
        assert not SlugPattern.match("Invalid Slug!")

    def test_platform_enum_values(self):
        card = CardCreate(
            slug="test-slug",
            title="Test",
            platform=Platform.YOUTUBE,
        )
        assert card.platform.value == "youtube"


class TestSourceSchemas:
    def test_valid_source_create(self):
        data = SourceCreate(
            url="https://www.nature.com/articles/s41586-023-06501-x",
            source_type=SourceType.PEER_REVIEWED,
        )
        assert data.url == "https://www.nature.com/articles/s41586-023-06501-x"
        assert data.source_type == SourceType.PEER_REVIEWED
        assert data.is_pivot is False
        assert data.parent_source_id is None

    def test_source_with_all_fields(self):
        # NOTE: authority_level is legacy (cf. ADR-017 / STATE.md). Kept in
        # the schema for backward compatibility but no longer used by the UI.
        # New code should rely on the typed indicators (citations_count,
        # impact_factor, subscribers_count, views_count) on SourceResponse.
        data = SourceCreate(
            url="https://example.com/article",
            title="Example Article",
            authors="John Doe, Jane Smith",
            source_type=SourceType.INSTITUTIONAL,
            authority_level="high",
            annotation="Important source for the argument",
            is_pivot=True,
        )
        assert data.is_pivot is True
        assert data.annotation == "Important source for the argument"

    def test_source_type_enum(self):
        source = SourceCreate(
            url="https://example.com",
            source_type=SourceType.PRESS,
        )
        assert source.source_type.value == "press"

    def test_url_is_stored_as_plain_string(self):
        """url is intentionally typed `str`, not HttpUrl: validation happens at
        the endpoint boundary (via HttpUrl + SSRF guard in url_extractor.py).
        This test pins the design so that a future "tightening" PR has to
        confront the migration cost of existing rows."""
        source = SourceCreate(
            url="not-a-valid-url",
            source_type=SourceType.PRESS,
        )
        assert isinstance(source.url, str)
        assert source.url == "not-a-valid-url"

    def test_url_field_constraints_are_lost_on_subclass(self):
        """SourceCreate redefines `url: str` which discards the
        `Field(min_length=1, max_length=2000)` declared on SourceBase.
        This means string-length validation does NOT happen at schema
        level — the endpoint must enforce it (currently it does not
        explicitly, but FastAPI rejects oversized bodies via its own
        request-size limit). Documented as a gap in the PR description.
        This test pins current behavior so a future fix is conscious."""
        long_url = "https://example.com/" + ("x" * 2001)
        # No ValidationError raised — the override stripped the constraint.
        SourceCreate(url=long_url, source_type=SourceType.PRESS)
        SourceCreate(url="", source_type=SourceType.PRESS)

    def test_parent_source_id_accepts_uuid(self):
        parent_id = uuid4()
        source = SourceCreate(
            url="https://example.com/child",
            source_type=SourceType.PRESS,
            parent_source_id=parent_id,
        )
        assert source.parent_source_id == parent_id

    def test_source_update_partial(self):
        """SourceUpdate must accept any subset of fields without requiring url."""
        update = SourceUpdate(title="New title", is_pivot=True)
        assert update.title == "New title"
        assert update.is_pivot is True
        assert update.annotation is None
