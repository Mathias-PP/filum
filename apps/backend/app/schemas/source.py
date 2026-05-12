from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


class SourceType(str, Enum):
    PEER_REVIEWED = "peer-reviewed"
    INSTITUTIONAL = "institutional"
    PRESS = "press"
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
    url: str = StringConstraints(min_length=1, max_length=2000)
    title: str | None = StringConstraints(max_length=500)
    authors: str | None = StringConstraints(max_length=500)
    published_at: datetime | None = None
    source_type: SourceType
    authority_level: AuthorityLevel = AuthorityLevel.MEDIUM
    annotation: str | None = StringConstraints(max_length=500)
    is_pivot: bool = False


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
    created_at: datetime
    updated_at: datetime | None


class SourceDetail(SourceResponse):
    position: int
    biblio_card_id: UUID
