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
async def test_linked_accounts_requires_auth(client):
    response = await client.get("/api/v1/users/me/linked-accounts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_then_get_linked_accounts(client, session_token):
    client.cookies.set("filum_session", session_token)
    payload = {
        "accounts": [
            {"platform": "youtube", "url": "https://youtube.com/@chan", "handle": "@chan"},
            {"platform": "x", "url": "https://x.com/someone", "handle": "@someone"},
        ]
    }
    response = await client.put("/api/v1/users/me/linked-accounts", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["platform"] == "youtube"
    assert body[0]["verified"] is False

    response = await client.get("/api/v1/users/me/linked-accounts")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_put_replaces_previous_list(client, session_token):
    client.cookies.set("filum_session", session_token)
    first = {"accounts": [{"platform": "tiktok", "url": "https://tiktok.com/@a"}]}
    await client.put("/api/v1/users/me/linked-accounts", json=first)

    second = {"accounts": [{"platform": "site", "url": "https://example.org"}]}
    response = await client.put("/api/v1/users/me/linked-accounts", json=second)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["platform"] == "site"


@pytest.mark.asyncio
async def test_put_dedupes_and_validates(client, session_token):
    client.cookies.set("filum_session", session_token)
    dup = {
        "accounts": [
            {"platform": "youtube", "url": "https://youtube.com/@chan"},
            {"platform": "youtube", "url": "https://youtube.com/@chan"},
        ]
    }
    response = await client.put("/api/v1/users/me/linked-accounts", json=dup)
    assert response.status_code == 200
    assert len(response.json()) == 1

    bad = {"accounts": [{"platform": "youtube", "url": "javascript:alert(1)"}]}
    response = await client.put("/api/v1/users/me/linked-accounts", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_public_profile_exposes_linked_accounts(client, session_token, test_user):
    client.cookies.set("filum_session", session_token)
    payload = {"accounts": [{"platform": "youtube", "url": "https://youtube.com/@chan"}]}
    await client.put("/api/v1/users/me/linked-accounts", json=payload)

    response = await client.get(f"/api/v1/users/@{test_user.username}")
    assert response.status_code == 200
    accounts = response.json()["linked_accounts"]
    assert len(accounts) == 1
    assert accounts[0]["platform"] == "youtube"
    assert accounts[0]["verified"] is False
