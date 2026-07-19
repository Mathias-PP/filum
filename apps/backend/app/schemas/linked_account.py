from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LinkedPlatform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    X = "x"
    TIKTOK = "tiktok"
    TWITCH = "twitch"
    SITE = "site"


class LinkedAccountIn(BaseModel):
    platform: LinkedPlatform
    url: str = Field(min_length=8, max_length=500)
    handle: str | None = Field(default=None, max_length=100)

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class LinkedAccountsUpdate(BaseModel):
    accounts: list[LinkedAccountIn] = Field(max_length=12)


class LinkedAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: LinkedPlatform
    url: str
    handle: str | None
    verified: bool = False
