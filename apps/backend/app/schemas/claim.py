from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ClaimRequestCreate(BaseModel):
    email: EmailStr
    channel_url: str = Field(min_length=8, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)


class ClaimRequestResponse(BaseModel):
    ok: bool = True
