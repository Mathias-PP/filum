from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_join_waitlist_creates_entry(client, db_session):
    from app.models.waitlist_entry import WaitlistEntry

    resp = await client.post("/api/v1/waitlist", json={"email": "Ada@Example.org"})
    assert resp.status_code == 201
    assert resp.json() == {"ok": True}
    entry = await db_session.scalar(select(WaitlistEntry))
    assert entry.email == "ada@example.org"  # normalise en lowercase
    assert entry.context == "home"


@pytest.mark.asyncio
async def test_join_waitlist_is_idempotent(client, db_session):
    from app.models.waitlist_entry import WaitlistEntry

    for _ in range(2):
        resp = await client.post("/api/v1/waitlist", json={"email": "ada@example.org"})
        assert resp.status_code == 201
    count = await db_session.scalar(select(func.count()).select_from(WaitlistEntry))
    assert count == 1


@pytest.mark.asyncio
async def test_join_waitlist_rejects_invalid_email(client):
    resp = await client.post("/api/v1/waitlist", json={"email": "pas-un-email"})
    assert resp.status_code == 422
