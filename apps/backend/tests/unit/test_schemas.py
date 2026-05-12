from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.user import SlugPattern
from app.schemas.biblio_card import CardCreate, Platform, ContentType
from app.schemas.source import SourceCreate, SourceType


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

    def test_source_with_all_fields(self):
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

    def test_url_is_string(self):
        source = SourceCreate(
            url="not-a-valid-url",
            source_type=SourceType.PRESS,
        )
        assert isinstance(source.url, str)
