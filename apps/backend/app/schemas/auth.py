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


# VerificationResponse removed: card-level /verify endpoint was deprecated
# in ADR-019 (pivot to content attestations). Use AttestationVerifyResponse
# for the current verification flow.


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
