from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.crypto.hashing import HashService
from app.crypto.keygen import KeyManager
from app.crypto.signing import Canonicalizer, SigningService
from app.models.content_attestation import ContentAttestation
from app.models.user import User

settings = get_settings()


class AttestationService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._key_manager = KeyManager(settings.master_encryption_key)

    async def create_attestation(self, user: User, content_url: str) -> ContentAttestation:
        now = datetime.now(UTC).replace(tzinfo=None)

        content_to_sign = {
            "user_id": str(user.id),
            "content_url": content_url,
            "attested_at": now.isoformat(),
        }
        canonical = Canonicalizer.canonicalize(content_to_sign)
        content_hash = HashService.sha256(canonical)

        private_pem = self._key_manager.decrypt_private_key(user.encrypted_private_key)
        signer = SigningService.from_pem(private_pem)
        signature = signer.sign(content_hash)

        attestation = ContentAttestation(
            user_id=user.id,
            content_url=content_url,
            attested_at=now,
            canonical_hash=content_hash,
            signature=signature,
        )
        self._db.add(attestation)
        await self._db.commit()
        await self._db.refresh(attestation)
        return attestation

    async def get_attestation(self, attestation_id: UUID) -> ContentAttestation | None:
        result = await self._db.execute(
            select(ContentAttestation)
            .options(selectinload(ContentAttestation.user))
            .where(ContentAttestation.id == attestation_id)
        )
        return result.scalar_one_or_none()

    async def verify_attestation(self, attestation: ContentAttestation) -> dict:
        content_to_sign = {
            "user_id": str(attestation.user_id),
            "content_url": attestation.content_url,
            "attested_at": attestation.attested_at.isoformat(),
        }
        canonical = Canonicalizer.canonicalize(content_to_sign)
        content_hash = HashService.sha256(canonical)

        if content_hash != attestation.canonical_hash:
            return {
                "valid": False,
                "reason": "hash_mismatch",
                "expected_hash": attestation.canonical_hash,
                "computed_hash": content_hash,
            }

        valid = SigningService.verify_with_public_key_hex(
            attestation.user.public_key, content_hash, attestation.signature
        )
        if not valid:
            return {
                "valid": False,
                "reason": "signature_mismatch",
            }

        return {
            "valid": True,
            "creator_slug": attestation.user.username,
            "content_url": attestation.content_url,
            "attested_at": attestation.attested_at.isoformat(),
            "public_key": attestation.user.public_key,
        }
