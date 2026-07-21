from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.user import SlugPattern
from app.schemas.biblio_card import CardCreate, Platform, ContentType
from app.schemas.source import (
    AuthorKind,
    SourceCategory,
    SourceCreate,
    SourceFormat,
    SourceUpdate,
)


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


def _minimal_source_kwargs(**overrides):
    """Helper: minimal valid SourceCreate kwargs with the 3-axis taxonomy."""
    base = {
        "url": "https://example.com/article",
        "format": SourceFormat.TEXTE,
        "category": SourceCategory.ARTICLE_SCIENTIFIQUE,
        "author_kind": AuthorKind.CHERCHEUR,
    }
    base.update(overrides)
    return base


class TestSourceSchemas:
    def test_valid_source_create(self):
        data = SourceCreate(**_minimal_source_kwargs(
            url="https://www.nature.com/articles/s41586-023-06501-x"
        ))
        assert data.url == "https://www.nature.com/articles/s41586-023-06501-x"
        assert data.format == SourceFormat.TEXTE
        assert data.category == SourceCategory.ARTICLE_SCIENTIFIQUE
        assert data.author_kind == AuthorKind.CHERCHEUR
        assert data.is_pivot is False
        assert data.parent_source_id is None

    def test_source_with_all_fields(self):
        data = SourceCreate(**_minimal_source_kwargs(
            title="Example Article",
            authors="John Doe, Jane Smith",
            format=SourceFormat.VIDEO,
            category=SourceCategory.DOCUMENTAIRE,
            author_kind=AuthorKind.MEDIA,
            annotation="Important source for the argument",
            is_pivot=True,
        ))
        assert data.is_pivot is True
        assert data.annotation == "Important source for the argument"
        assert data.format.value == "video"

    def test_format_enum_values(self):
        source = SourceCreate(**_minimal_source_kwargs(format=SourceFormat.AUDIO))
        assert source.format.value == "audio"

    def test_category_enum_values(self):
        source = SourceCreate(**_minimal_source_kwargs(category=SourceCategory.PODCAST))
        assert source.category.value == "podcast"

    def test_author_kind_enum_values(self):
        source = SourceCreate(**_minimal_source_kwargs(author_kind=AuthorKind.MEDIA))
        assert source.author_kind.value == "media"

    def test_url_is_stored_as_plain_string(self):
        """url is intentionally typed `str`, not HttpUrl: validation happens at
        the endpoint boundary (via HttpUrl + SSRF guard in url_extractor.py)."""
        source = SourceCreate(**_minimal_source_kwargs(url="not-a-valid-url"))
        assert isinstance(source.url, str)
        assert source.url == "not-a-valid-url"

    def test_url_max_length_enforced(self):
        too_long = "https://example.com/" + ("x" * 2001)
        with pytest.raises(ValidationError):
            SourceCreate(**_minimal_source_kwargs(url=too_long))

    def test_url_min_length_enforced(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_minimal_source_kwargs(url=""))

    def test_parent_source_id_accepts_uuid(self):
        parent_id = uuid4()
        source = SourceCreate(**_minimal_source_kwargs(parent_source_id=parent_id))
        assert source.parent_source_id == parent_id

    def test_source_update_partial(self):
        """SourceUpdate must accept any subset of fields without requiring url."""
        update = SourceUpdate(title="New title", is_pivot=True)
        assert update.title == "New title"
        assert update.is_pivot is True
        assert update.annotation is None

    def test_published_at_tz_aware_normalized_to_naive_utc(self):
        # Colonne Postgres TIMESTAMP WITHOUT TIME ZONE : une datetime tz-aware
        # ("2002-01-01T00:00:00Z" côté client) fait planter asyncpg (DataError).
        source = SourceCreate(**_minimal_source_kwargs(published_at="2002-01-01T00:00:00Z"))
        assert source.published_at is not None
        assert source.published_at.tzinfo is None
        assert source.published_at.isoformat() == "2002-01-01T00:00:00"

    def test_published_at_offset_converted_to_utc(self):
        source = SourceCreate(**_minimal_source_kwargs(published_at="2014-06-01T02:00:00+02:00"))
        assert source.published_at is not None
        assert source.published_at.tzinfo is None
        assert source.published_at.isoformat() == "2014-06-01T00:00:00"

    def test_published_at_naive_passthrough(self):
        source = SourceCreate(**_minimal_source_kwargs(published_at="2014-06-01T12:00:00"))
        assert source.published_at is not None
        assert source.published_at.tzinfo is None

    def test_source_update_published_at_tz_aware_normalized(self):
        update = SourceUpdate(published_at="1999-12-31T23:00:00+01:00")
        assert update.published_at is not None
        assert update.published_at.tzinfo is None
        assert update.published_at.isoformat() == "1999-12-31T22:00:00"
