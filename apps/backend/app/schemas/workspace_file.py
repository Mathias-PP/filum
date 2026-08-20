from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_CONTENT_MAX = 1_000_000


class WorkspaceFileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=_CONTENT_MAX)


class WorkspaceFileRead(BaseModel):
    path: str
    sha256: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceTreeEntry(BaseModel):
    path: str
    type: Literal["file", "directory"]
    sha256: str | None = None
    updated_at: datetime | None = None
