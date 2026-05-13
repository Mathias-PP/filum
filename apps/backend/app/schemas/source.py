from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    PEER_REVIEWED = "peer-reviewed"
    INSTITUTIONAL = "institutional"
    PRESS = "press"
    VIDEO = "video"
    IMAGE = "image"
    ORIGINAL = "original"


class AuthorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ArchiveStatus(str, Enum):
    PENDING = "pending"
    ARCHIVED = "archived"
    FAILED = "failed"


class SourceBase(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    authors: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    source_type: SourceType
    authority_level: AuthorityLevel = AuthorityLevel.MEDIUM
    annotation: str | None = Field(default=None, max_length=500)
    is_pivot: bool = False
    parent_source_id: UUID | None = None


class SourceCreate(SourceBase):
    url: str


class SourceUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    published_at: datetime | None = None
    source_type: SourceType | None = None
    authority_level: AuthorityLevel | None = None
    annotation: str | None = None
    is_pivot: bool | None = None
    parent_source_id: UUID | None = None


class SourceExcerptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    text: str
    suggested_by_ai: bool


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    title: str | None
    authors: str | None
    published_at: datetime | None
    source_type: SourceType
    authority_level: AuthorityLevel
    annotation: str | None
    is_pivot: bool
    archive_status: ArchiveStatus
    archive_url: str | None
    archive_timestamp: datetime | None
    parent_source_id: UUID | None
    conflict_of_interest: str | None = None
    citations_count: int | None = None
    subscribers_count: int | None = None
    views_count: int | None = None
    impact_factor: float | None = None
    excerpts: list[SourceExcerptResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None


class SourceDetail(SourceResponse):
    position: int
    biblio_card_id: UUID
