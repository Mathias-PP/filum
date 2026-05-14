from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceFormat(str, Enum):
    TEXTE = "texte"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    DATA = "data"


class SourceCategory(str, Enum):
    ARTICLE_SCIENTIFIQUE = "article-scientifique"
    PREPRINT = "preprint"
    ARTICLE_PRESSE = "article-presse"
    COMMUNIQUE = "communique"
    DOCUMENTAIRE = "documentaire"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    BLOG = "blog"
    POST_SOCIAL = "post-social"
    LIVRE = "livre"
    PAGE_WEB = "page-web"
    NOTES = "notes"


class AuthorKind(str, Enum):
    CHERCHEUR = "chercheur"
    MEDIA = "media"
    INSTITUTION_PUBLIQUE = "institution-publique"
    GOUVERNEMENT = "gouvernement"
    ECOLE = "ecole"
    LABORATOIRE = "laboratoire"
    ENTREPRISE = "entreprise"
    ASSO = "asso"
    INDIVIDU = "individu"


class ArchiveStatus(str, Enum):
    PENDING = "pending"
    ARCHIVED = "archived"
    FAILED = "failed"


class SourceBase(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    authors: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    format: SourceFormat
    category: SourceCategory
    author_kind: AuthorKind
    annotation: str | None = Field(default=None, max_length=500)
    is_pivot: bool = False
    parent_source_id: UUID | None = None


class SourceCreate(SourceBase):
    # No fields are added here. The previous `url: str` override silently
    # discarded the Field(min_length=1, max_length=2000) inherited from
    # SourceBase (Pydantic v2 replaces fields, doesn't merge). Removed
    # so input validation actually applies on the API boundary.
    pass


class SourceUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    published_at: datetime | None = None
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None
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
    format: SourceFormat
    category: SourceCategory
    author_kind: AuthorKind
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
