from __future__ import annotations

from cryptography.hazmat.primitives import hashes


class HashService:
    @staticmethod
    def sha256(data: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        digest = hashes.Hash(hashes.SHA256())
        digest.update(data)
        return digest.finalize().hex()
