from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyManager:
    def __init__(self, encryption_key: str):
        key_bytes = encryption_key.encode("utf-8")
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b"\0")
        self._aesgcm = AESGCM(key_bytes[:32])

    @staticmethod
    def generate_keypair() -> tuple[str, str, str]:
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        public_key_raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

        return private_pem, public_pem, public_key_raw

    def encrypt_private_key(self, private_key_pem: str) -> str:
        nonce = os.urandom(12)
        encrypted = self._aesgcm.encrypt(nonce, private_key_pem.encode("utf-8"), None)
        return base64.b64encode(nonce + encrypted).decode("utf-8")

    def decrypt_private_key(self, encrypted_pem: str) -> str:
        data = base64.b64decode(encrypted_pem.encode("utf-8"))
        nonce = data[:12]
        ciphertext = data[12:]
        decrypted = self._aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
