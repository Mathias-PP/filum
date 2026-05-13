from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class Canonicalizer:
    @staticmethod
    def canonicalize(obj: dict[str, Any]) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class SigningService:
    def __init__(self, private_key: ed25519.Ed25519PrivateKey):
        self._private_key = private_key

    @classmethod
    def from_pem(cls, pem_data: str) -> SigningService:
        private_key = serialization.load_pem_private_key(
            pem_data.encode("utf-8"),
            password=None,
        )
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("Invalid Ed25519 private key")
        return cls(private_key)

    def sign(self, data: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        signature = self._private_key.sign(data)
        return signature.hex()

    def get_public_key(self) -> str:
        return (
            self._private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            .hex()
        )

    def verify(self, data: str | bytes, signature: str) -> bool:
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            signature_bytes = bytes.fromhex(signature)
            public_key = self._private_key.public_key()
            public_key.verify(signature_bytes, data)
            return True
        except Exception:
            return False

    @staticmethod
    def verify_with_public_key_hex(
        public_key_hex: str, data: str | bytes, signature: str
    ) -> bool:
        """Verify an Ed25519 signature using a raw public key stored as hex.

        Used by CardService.verify_card(): we only have the user's raw public
        key (64 hex chars = 32 bytes), not a private PEM. Wrapping the raw key
        in `BEGIN PRIVATE KEY` headers and calling from_pem() — as the old
        verify_card code did — always fails, so signed cards were silently
        unverifiable in production.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(public_key_hex)
            )
            public_key.verify(bytes.fromhex(signature), data)
            return True
        except Exception:
            return False
