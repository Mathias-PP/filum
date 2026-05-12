from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.crypto.hashing import HashService, SigningService, Canonicalizer
from app.crypto.keygen import KeyManager


class TestHashService:
    def test_sha256_string(self):
        result = HashService.sha256("hello world")
        assert len(result) == 64
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_sha256_bytes(self):
        result = HashService.sha256(b"hello world")
        assert len(result) == 64

    def test_sha256_consistency(self):
        data = "test data for hashing"
        result1 = HashService.sha256(data)
        result2 = HashService.sha256(data)
        assert result1 == result2

    def test_sha256_different_inputs(self):
        hash1 = HashService.sha256("input1")
        hash2 = HashService.sha256("input2")
        assert hash1 != hash2


class TestCanonicalizer:
    def test_canonicalize_basic(self):
        data = {"b": 2, "a": 1}
        result = Canonicalizer.canonicalize(data)
        assert '"a":1' in result
        assert '"b":2' in result
        assert result.index('"a"') < result.index('"b"')

    def test_canonicalize_nested(self):
        data = {"outer": {"inner": "value"}, "array": [1, 2, 3]}
        result = Canonicalizer.canonicalize(data)
        assert '"outer":{"inner":"value"}' in result
        assert '"array":[1,2,3]' in result


class TestSigningService:
    def test_sign_and_verify(self):
        private_key = ed25519.Ed25519PrivateKey.generate()
        service = SigningService(private_key)

        message = "Test message for signing"
        signature = service.sign(message)

        assert len(signature) == 128
        assert service.verify(message, signature)

    def test_verify_wrong_signature(self):
        private_key = ed25519.Ed25519PrivateKey.generate()
        service = SigningService(private_key)

        assert not service.verify("message", "invalid_signature")

    def test_get_public_key(self):
        private_key = ed25519.Ed25519PrivateKey.generate()
        service = SigningService(private_key)

        public_key = service.get_public_key()
        assert len(public_key) == 64


class TestKeyManager:
    def test_generate_keypair(self):
        private_pem, public_pem, public_key_raw = KeyManager.generate_keypair()

        assert "-----BEGIN PRIVATE KEY-----" in private_pem
        assert "-----END PRIVATE KEY-----" in private_pem
        assert "-----BEGIN PUBLIC KEY-----" in public_pem
        assert len(public_key_raw) == 64

    def test_encrypt_decrypt_private_key(self):
        encryption_key = KeyManager.generate_keypair()[0][:32]
        key_manager = KeyManager(encryption_key)

        private_pem, _, _ = KeyManager.generate_keypair()
        encrypted = key_manager.encrypt_private_key(private_pem)

        assert encrypted != private_pem

        decrypted = key_manager.decrypt_private_key(encrypted)
        assert decrypted == private_pem

    def test_wrong_encryption_key(self):
        encrypt_key = KeyManager.generate_keypair()[0][:32]
        key_manager = KeyManager(encrypt_key)

        private_pem, _, _ = KeyManager.generate_keypair()
        encrypted = key_manager.encrypt_private_key(private_pem)

        wrong_key_manager = KeyManager("wrong_key_for_decryption_test")
        with pytest.raises(Exception):
            wrong_key_manager.decrypt_private_key(encrypted)
