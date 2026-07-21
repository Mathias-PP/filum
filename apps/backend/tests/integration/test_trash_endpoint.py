"""Endpoint GET /cards/deleted (corbeille).

Verifie :
- Auth requise.
- Ne renvoie que les fiches soft-deletees de l'user connecte.
- Ordre : plus recemment supprimee en premier.
- Le path 'deleted' n'est pas confondu avec /cards/{card_id} (UUID parse).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


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


@pytest_asyncio.fixture
async def deleted_cards(db_session, test_user):
    """Cree 2 fiches soft-deletees a 5 minutes d'ecart."""
    from app.models.biblio_card import BiblioCard

    now = datetime.now(UTC).replace(tzinfo=None)
    older = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-old",
        title="Ancienne fiche",
        content_type="article",
        platform="blog",
        status="draft",
        deleted_at=now - timedelta(minutes=5),
    )
    newer = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-new",
        title="Nouvelle fiche",
        content_type="article",
        platform="blog",
        status="draft",
        deleted_at=now,
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    return [older, newer]


@pytest.mark.asyncio
async def test_list_deleted_cards_requires_auth(client):
    resp = await client.get("/api/v1/cards/deleted")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_deleted_cards_returns_only_soft_deleted(
    client, session_token, deleted_cards
):
    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/deleted")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [c["slug"] for c in body]
    # Ordre : plus recemment supprimee en premier
    assert slugs == ["fiche-new", "fiche-old"]


@pytest.mark.asyncio
async def test_list_deleted_cards_excludes_non_deleted(
    client, session_token, db_session, test_user
):
    """Une fiche NON deletee n'apparait pas dans la corbeille."""
    from app.models.biblio_card import BiblioCard

    live = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-live",
        title="Fiche vivante",
        content_type="article",
        platform="blog",
        status="draft",
    )
    db_session.add(live)
    await db_session.commit()

    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/deleted")
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    assert "fiche-live" not in slugs


@pytest.mark.asyncio
async def test_deleted_path_not_confused_with_uuid_param(client, session_token):
    """/cards/deleted matche l'endpoint corbeille, pas /cards/{card_id}."""
    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/deleted")
    # Si mal ordonne, FastAPI parse 'deleted' comme UUID -> 422
    assert resp.status_code != 422
