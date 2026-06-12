from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.source import SourceResponse


class Platform(str, Enum):
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    BLOG = "blog"
    X = "x"
    BLUESKY = "bluesky"
    OTHER = "other"


class ContentType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    POST = "post"
    PODCAST = "podcast"
    OTHER = "other"


class CardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


SlugPattern = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class CardBase(BaseModel):
    slug: str = Field(min_length=3, max_length=100, pattern=SlugPattern)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    content_url: str | None = None
    platform: Platform = Platform.OTHER
    content_type: ContentType = ContentType.VIDEO


class CardCreate(CardBase):
    pass


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    content_url: str | None = None
    platform: Platform | None = None


class CardStats(BaseModel):
    total_sources: int = 0
    chercheur: int = 0
    media: int = 0
    institution_publique: int = 0
    individu: int = 0
    archived_count: int = 0
    all_archived: bool = False


class CreatorInfo(BaseModel):
    slug: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    public_key: str


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str | None
    content_url: str | None
    platform: Platform
    content_type: ContentType
    status: CardStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class CardDetail(CardResponse):
    creator: CreatorInfo
    sources: list[SourceResponse]
    stats: CardStats


class CardPublish(BaseModel):
    status: CardStatus = CardStatus.PUBLISHED
    published_at: datetime
    public_url: str


class CardListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    status: CardStatus
    published_at: datetime | None
    total_sources: int = 0
