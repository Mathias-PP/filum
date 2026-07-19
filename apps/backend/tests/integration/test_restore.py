from __future__ import annotations

from uuid import uuid4

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


@pytest_asyncio.fixture
async def draft_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-restaurable",
        title="Fiche restaurable",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_restore_requires_auth(client, draft_card):
    resp = await client.post(f"/api/v1/cards/{draft_card.id}/restore")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_restore_404_when_not_deleted(client, session_token, draft_card):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{draft_card.id}/restore")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_then_restore_roundtrip(client, session_token, draft_card):
    client.cookies.set("filum_session", session_token)

    resp = await client.delete(f"/api/v1/cards/{draft_card.id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/cards/{draft_card.id}")
    assert resp.status_code == 404

    resp = await client.post(f"/api/v1/cards/{draft_card.id}/restore")
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"

    resp = await client.get(f"/api/v1/cards/{draft_card.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_restore_forbidden_for_other_user(client, db_session, session_token, draft_card):
    from app.models.user import User
    from app.services.auth import AuthService

    client.cookies.set("filum_session", session_token)
    resp = await client.delete(f"/api/v1/cards/{draft_card.id}")
    assert resp.status_code == 204

    other = User(
        id=uuid4(),
        email="other@example.com",
        username="otheruser",
        display_name="Other",
        public_key="o" * 64,
        encrypted_private_key="encrypted_other_key",
        google_id="google_other_456",
        is_verified=True,
    )
    db_session.add(other)
    await db_session.commit()
    token = AuthService(db_session).create_session(other.id)

    client.cookies.set("filum_session", token)
    resp = await client.post(f"/api/v1/cards/{draft_card.id}/restore")
    # 404 (pas 403) : ne revele pas l'existence d'une fiche d'autrui.
    assert resp.status_code == 404
