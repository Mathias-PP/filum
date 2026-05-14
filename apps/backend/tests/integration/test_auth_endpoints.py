from __future__ import annotations

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


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_me_with_valid_cookie_returns_user(client, session_token, test_user):
    client.cookies.set("filum_session", session_token)
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == test_user.email
    assert body["username"] == test_user.username


@pytest.mark.asyncio
async def test_logout_clears_session_cookie(client, session_token):
    client.cookies.set("filum_session", session_token)
    response = await client.post("/api/v1/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    set_cookie = response.headers.get("set-cookie", "")
    assert "filum_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=Thu, 01 Jan 1970" in set_cookie.lower()
