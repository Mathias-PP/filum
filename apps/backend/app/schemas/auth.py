from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: UUID
    exp: datetime
    iat: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


class VerificationResponse(BaseModel):
    valid: bool
    creator_slug: str | None = None
    card_slug: str | None = None
    content_hash: str | None = None
    signature: str | None = None
    signed_at: datetime | None = None
    details: dict | None = None
    reason: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
