from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AttestationCreate(BaseModel):
    content_url: str


class AttestationResponse(BaseModel):
    id: UUID
    user_id: UUID
    content_url: str
    attested_at: datetime
    canonical_hash: str
    signature: str
    created_at: datetime | None


class AttestationVerifyResponse(BaseModel):
    valid: bool
    attestation_id: UUID | None = None
    content_url: str | None = None
    creator_slug: str | None = None
    public_key: str | None = None
    hash_algorithm: str = "SHA-256"
    signature_algorithm: str = "Ed25519"
    canonicalization: str = "RFC 8785 JSON Canonicalization Scheme"
    reason: str | None = None
