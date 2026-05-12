from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from jose import jwt
from starlette.datastructures import Headers
from starlette.requests import Request

from app.schemas.auth import LoginResponse, TokenPayload


class TestAuthService:
    async def test_create_session_returns_valid_jwt(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        from app.services.auth import settings

        payload = jwt.decode(
            token, settings.session_secret, algorithms=["HS256"],
        )
        assert payload["sub"] == str(test_user.id)
        assert "exp" in payload
        assert "iat" in payload

    async def test_create_session_expiry_is_24h(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        payload = jwt.decode(
            token, "test-secret-for-ci-session-32chars", algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        iat = datetime.fromtimestamp(payload["iat"], tz=UTC)
        assert exp - iat <= timedelta(hours=24)

    async def test_get_current_user_from_cookie(self, auth_service, test_user):
        token = auth_service.create_session(test_user.id)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        request._cookies = {"filum_session": token}
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
        expired_token = jwt.encode(
            expired_payload, settings.session_secret, algorithm=ALGORITHM
        )
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

        result = await db_session.execute(
            select(User).where(User.google_id == "new_google_id_456")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.email == "newuser@example.com"

    async def test_create_user_from_google_generates_keypair(self, auth_service):
        user = await auth_service.create_user_from_google(
            email="keytest@example.com",
            google_id="key_test_id",
            username="keytest",
            display_name="Key Test",
        )
        assert len(user.public_key) == 64
        assert "ENCRYPTED" not in user.public_key
        assert user.encrypted_private_key != user.public_key


class TestAuthSchemas:
    def test_token_payload_valid(self):
        now = datetime.now(UTC)
        payload = TokenPayload(
            sub=uuid4(),
            exp=now + timedelta(hours=1),
            iat=now,
        )
        assert payload.sub is not None
        assert isinstance(payload.sub, UUID)
        assert payload.exp > payload.iat

    def test_login_response_serialization(self):
        user_id = uuid4()
        response = LoginResponse(
            access_token="test_token_value",
            token_type="bearer",
            user_id=user_id,
        )
        assert response.access_token == "test_token_value"
        assert response.token_type == "bearer"
        assert response.user_id == user_id
