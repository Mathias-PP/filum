from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class WaitlistCreate(BaseModel):
    email: EmailStr
    context: str = Field(default="home", max_length=50)


class WaitlistResponse(BaseModel):
    ok: bool = True
