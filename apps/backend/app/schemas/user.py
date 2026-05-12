from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints
import re


SlugPattern = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class UserBase(BaseModel):
    username: str = StringConstraints(min_length=3, max_length=100, pattern=SlugPattern)
    display_name: str | None = None
    bio: str | None = None


class UserCreate(UserBase):
    email: EmailStr
    google_id: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    is_verified: bool
    created_at: datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    public_key: str
    is_verified: bool
