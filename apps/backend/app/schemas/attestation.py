from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttestationCreate(BaseModel):
    # Une attestation avec content_url vide n'atteste rien : le triplet
    # (user_id, "", attested_at) serait signe sans porter de reference au
    # contenu. Le contrat impose une URL non-vide bornee (au-dela de 2000
    # caracteres, ce n'est plus une URL utilisable).
    content_url: str = Field(min_length=1, max_length=2000)


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
