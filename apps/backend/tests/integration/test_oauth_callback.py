from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


GOOGLE_PAYLOAD = {
    "sub": "google_test_sub_123",
    "email": "oauth_new@example.com",
    "name": "OAuth New User",
    "picture": "https://example.com/pic.jpg",
    "iss": "https://accounts.google.com",
    "aud": "",
}


@pytest.mark.asyncio
async def test_google_login_redirects_and_sets_state_cookie(client):
    response = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location
    assert "state=" in location
    assert "filum_oauth_state" in response.cookies


@pytest.mark.asyncio
async def test_google_callback_without_state_cookie_returns_400(client):
    response = await client.get(
        "/api/v1/auth/google/callback?code=test_code&state=test_state",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_state"


@pytest.mark.asyncio
async def test_google_callback_mismatched_state_returns_400(client):
    client.cookies.set("filum_oauth_state", "real_state")
    response = await client.get(
        "/api/v1/auth/google/callback?code=test_code&state=wrong_state",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_state"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.jwt.decode")
@patch("app.api.v1.endpoints.auth.PyJWKClient")
@patch("app.api.v1.endpoints.auth.httpx")
async def test_google_callback_creates_new_user(
    mock_httpx_module,
    mock_jwks_client_cls,
    mock_jwt_decode,
    client,
    db_session,
):
    state = "test_valid_state"
    client.cookies.set("filum_oauth_state", state)

    mock_httpx_client = AsyncMock()
    mock_httpx_module.AsyncClient.return_value.__aenter__.return_value = mock_httpx_client
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "id_token": "fake_id_token_value",
        "access_token": "fake_access_token",
    }
    mock_httpx_client.post.return_value = mock_token_response

    mock_signing_key = MagicMock()
    mock_signing_key.key = "fake_signing_key"
    mock_jwks_client_cls.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

    mock_jwt_decode.return_value = {
        **GOOGLE_PAYLOAD,
        "aud": "",
    }

    response = await client.get(
        f"/api/v1/auth/google/callback?code=test_code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers.get("location", "")
    assert location == "http://localhost:5173/auth/callback"

    set_cookie = response.headers.get("set-cookie", "")
    assert "filum_session=" in set_cookie

    from sqlalchemy import select
    from app.models.user import User

    result = await db_session.execute(select(User).where(User.google_id == "google_test_sub_123"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email == "oauth_new@example.com"
    assert user.display_name == "OAuth New User"
    assert user.avatar_url == "https://example.com/pic.jpg"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.jwt.decode")
@patch("app.api.v1.endpoints.auth.PyJWKClient")
@patch("app.api.v1.endpoints.auth.httpx")
async def test_google_callback_returns_existing_user(
    mock_httpx_module,
    mock_jwks_client_cls,
    mock_jwt_decode,
    client,
    test_user,
):
    state = "test_valid_state_2"
    client.cookies.set("filum_oauth_state", state)

    mock_httpx_client = AsyncMock()
    mock_httpx_module.AsyncClient.return_value.__aenter__.return_value = mock_httpx_client
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "id_token": "fake_id_token_2",
        "access_token": "fake_access_token",
    }
    mock_httpx_client.post.return_value = mock_token_response

    mock_signing_key = MagicMock()
    mock_signing_key.key = "fake_signing_key"
    mock_jwks_client_cls.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

    mock_jwt_decode.return_value = {
        "sub": test_user.google_id,
        "email": test_user.email,
        "name": test_user.display_name,
        "picture": None,
        "iss": "https://accounts.google.com",
        "aud": "",
    }

    response = await client.get(
        f"/api/v1/auth/google/callback?code=test_code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers.get("location", "") == "http://localhost:5173/auth/callback"
    assert "filum_session=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.httpx")
async def test_google_callback_token_exchange_failure(
    mock_httpx_module,
    client,
):
    state = "test_valid_state_3"
    client.cookies.set("filum_oauth_state", state)

    mock_httpx_client = AsyncMock()
    mock_httpx_module.AsyncClient.return_value.__aenter__.return_value = mock_httpx_client
    mock_token_response = MagicMock()
    mock_token_response.status_code = 400
    mock_httpx_client.post.return_value = mock_token_response

    response = await client.get(
        f"/api/v1/auth/google/callback?code=bad_code&state={state}",
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_google_callback_with_error_param_returns_400(client):
    response = await client.get(
        "/api/v1/auth/google/callback?error=access_denied",
    )
    assert response.status_code == 400
    body = response.json()
    assert "access_denied" in body["error"]["message"]
