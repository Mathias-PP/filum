from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from starlette.requests import Request

from app.schemas.auth import TokenPayload
from app.services.auth import ALGORITHM, SESSION_EXPIRE_HOURS, settings


class TestAuthService:
    async def test_create_session_returns_valid_jwt(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        assert payload["sub"] == str(test_user.id)
        assert "exp" in payload
        assert "iat" in payload

    async def test_create_session_expiry_is_24h(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        iat = datetime.fromtimestamp(payload["iat"], tz=UTC)
        delta = exp - iat
        expected = timedelta(hours=SESSION_EXPIRE_HOURS)
        assert expected - timedelta(seconds=2) <= delta <= expected

    async def test_get_current_user_from_cookie(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"filum_session={token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is not None
        assert user.id == test_user.id
        assert user.email == "test@example.com"

    async def test_get_current_user_from_bearer(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is not None
        assert user.id == test_user.id

    async def test_get_current_user_no_token(self, auth_service):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is None

    async def test_get_current_user_invalid_token(self, auth_service):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", b"filum_session=invalid_token_value")],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is None

    async def test_get_current_user_expired_token(self, auth_service, test_user):
        from app.services.auth import ALGORITHM, settings

        expire = datetime.now(UTC) - timedelta(hours=1)
        expired_payload = {
            "sub": str(test_user.id),
            "exp": expire,
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }
        expired_token = jwt.encode(expired_payload, settings.session_secret, algorithm=ALGORITHM)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"filum_session={expired_token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is None

    async def test_get_current_user_wrong_secret(self, auth_service, test_user):
        token = jwt.encode(
            {"sub": str(test_user.id)},
            "wrong-secret-key-that-is-32-chars-loooong",
            algorithm="HS256",
        )
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"filum_session={token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is None

    async def test_get_current_user_soft_deleted(self, auth_service, db_session, test_user):
        from datetime import datetime

        test_user.deleted_at = datetime.now(UTC)
        await db_session.commit()

        token = auth_service.create_session(test_user.id)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"filum_session={token}".encode())],
            "query_string": b"",
        }
        request = Request(scope)
        user = await auth_service.get_current_user(request)
        assert user is None

    async def test_get_user_by_google_id_found(self, auth_service, test_user):
        user = await auth_service.get_user_by_google_id("google_test_123")
        assert user is not None
        assert user.id == test_user.id

    async def test_get_user_by_google_id_not_found(self, auth_service):
        user = await auth_service.get_user_by_google_id("nonexistent_google_id")
        assert user is None

    async def test_create_user_from_google_creates_user(self, auth_service, db_session):
        from sqlalchemy import select

        from app.models.user import User

        user = await auth_service.create_user_from_google(
            email="newuser@example.com",
            google_id="new_google_id_456",
            username="newuser",
            display_name="New User",
        )
        assert user.email == "newuser@example.com"
        assert user.google_id == "new_google_id_456"
        assert user.username == "newuser"
        assert user.display_name == "New User"
        assert user.is_verified is True
        assert user.public_key is not None
        assert user.encrypted_private_key is not None
        assert user.id is not None

        result = await db_session.execute(select(User).where(User.google_id == "new_google_id_456"))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.email == "newuser@example.com"

    async def test_create_user_from_google_generates_usable_keypair(self, auth_service):
        from cryptography.hazmat.primitives.asymmetric import ed25519

        user = await auth_service.create_user_from_google(
            email="keytest@example.com",
            google_id="key_test_id",
            username="keytest",
            display_name="Key Test",
        )

        assert len(user.public_key) == 64
        assert bytes.fromhex(user.public_key)

        decrypted_pem = auth_service._key_manager.decrypt_private_key(user.encrypted_private_key)
        private_key = serialization.load_pem_private_key(
            decrypted_pem.encode("utf-8"), password=None
        )
        assert isinstance(private_key, ed25519.Ed25519PrivateKey)

        message = b"filum-provenance-test"
        signature = private_key.sign(message)

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(user.public_key))
        public_key.verify(signature, message)

    async def test_create_user_from_google_slugifies_dotted_email_local_part(self, auth_service):
        """Dots, plus-tags and other non-slug chars are rewritten to hyphens.
        Regression: a fresh login with e.g. mathias.pinault@gmail.com used to
        try to insert username="mathias.pinault" which doesn't match the
        public /@<username> slug pattern."""
        user = await auth_service.create_user_from_google(
            email="mathias.pinault@gmail.com",
            google_id="gmail-google-id-1",
            username="mathias.pinault",
            display_name="Mathias",
        )
        assert user.username == "mathias-pinault"

    async def test_create_user_from_google_resolves_username_collision(
        self, auth_service, db_session
    ):
        """Two distinct Google accounts whose email local part collides
        (e.g. mathias.pinault@hotmail.fr and mathias.pinault@gmail.com)
        must both succeed. Regression: the second one used to raise an
        IntegrityError on `username` UNIQUE, surfaced as a generic 500."""
        first = await auth_service.create_user_from_google(
            email="mathias.pinault@hotmail.fr",
            google_id="hotmail-google-id",
            username="mathias.pinault",
        )
        second = await auth_service.create_user_from_google(
            email="mathias.pinault@gmail.com",
            google_id="gmail-google-id-2",
            username="mathias.pinault",
        )
        assert first.username == "mathias-pinault"
        assert second.username == "mathias-pinault-2"
        assert first.id != second.id

    async def test_create_user_from_google_unusable_local_part_falls_back(self, auth_service):
        """If the slug after sanitization is empty (extreme edge case), the
        service falls back to a google_id-derived name rather than crashing."""
        user = await auth_service.create_user_from_google(
            email="++@example.com",
            google_id="weird-google-id-abc123",
            username="++",
        )
        assert user.username.startswith("user-")
        assert "weird-google-id-abc" in user.username or "weird-google" in user.username


class TestAuthSchemas:
    async def test_token_roundtrip_via_create_session(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        raw = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        payload = TokenPayload(
            sub=UUID(raw["sub"]),
            exp=datetime.fromtimestamp(raw["exp"], tz=UTC),
            iat=datetime.fromtimestamp(raw["iat"], tz=UTC),
        )
        assert payload.sub == test_user.id
        assert payload.exp > payload.iat
