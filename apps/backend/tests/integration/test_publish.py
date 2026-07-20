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
        slug="ma-fiche",
        title="Ma fiche",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest_asyncio.fixture
async def draft_card_with_source(db_session, draft_card):
    from app.models.source import Source

    source = Source(
        id=uuid4(),
        biblio_card_id=draft_card.id,
        url="https://example.org/etude",
        title="Une étude",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()
    return draft_card


@pytest.mark.asyncio
async def test_publish_requires_auth(client, draft_card_with_source):
    resp = await client.post(f"/api/v1/cards/{draft_card_with_source.id}/publish")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_publish_404_on_unknown_card(client, session_token):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{uuid4()}/publish")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_rejected_without_sources(client, session_token, draft_card):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{draft_card.id}/publish")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_publish_forbidden_for_other_user(client, db_session, draft_card_with_source):
    from app.models.user import User
    from app.services.auth import AuthService

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
    resp = await client.post(f"/api/v1/cards/{draft_card_with_source.id}/publish")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_publish_success(client, session_token, test_user, draft_card_with_source):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{draft_card_with_source.id}/publish")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None
    assert body["public_url"].endswith(f"/@{test_user.username}/{draft_card_with_source.slug}")

    # La fiche devient visible publiquement.
    resp = await client.get(f"/api/v1/@{test_user.username}/{draft_card_with_source.slug}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_published_card_is_modifiable_and_deletable(
    client, session_token, draft_card_with_source
):
    """Fiches publiees editables et soft-deletables par leur owner
    (2026-07-21) : la fiche est la vue produit, l'attestation Ed25519
    reste immuable dans content_attestations."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{draft_card_with_source.id}/publish")
    assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/cards/{draft_card_with_source.id}", json={"title": "Nouveau titre"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nouveau titre"

    resp = await client.delete(f"/api/v1/cards/{draft_card_with_source.id}")
    assert resp.status_code == 204
