from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


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
async def seed_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-seed",
        title="Fiche seed",
        content_type="video",
        platform="youtube",
        status="published",
        is_seed=True,
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_public_card_exposes_is_seed(client, seed_card, test_user):
    resp = await client.get(f"/api/v1/@{test_user.username}/{seed_card.slug}")
    assert resp.status_code == 200
    assert resp.json()["is_seed"] is True


@pytest.mark.asyncio
async def test_create_card_accepts_is_seed_true(client, session_token):
    """POST /cards accepte is_seed=true : l'utilisateur declare qu'il n'est
    pas l'auteur du contenu, la fiche est marquee comme non revendiquee."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-non-mienne",
            "title": "Un contenu d'un autre createur",
            "platform": "youtube",
            "content_type": "video",
            "is_seed": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_seed"] is True


@pytest.mark.asyncio
async def test_create_card_defaults_is_seed_false(client, session_token):
    """Sans is_seed dans le payload, la fiche est consideree comme owned."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "ma-fiche",
            "title": "Mon propre contenu",
            "platform": "blog",
            "content_type": "article",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_seed"] is False


@pytest.mark.asyncio
async def test_update_card_can_toggle_is_seed(client, session_token):
    """PATCH /cards/{id} permet de basculer is_seed (utile pour corriger
    apres coup si on s'est trompe a la creation). Test sur draft pour rester
    independant de la regle 'edition des fiches publiees'."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "seed-a-corriger",
            "title": "En fait c'est de moi",
            "platform": "blog",
            "content_type": "article",
            "is_seed": True,
        },
    )
    assert resp.status_code == 201
    card_id = resp.json()["id"]
    resp = await client.patch(f"/api/v1/cards/{card_id}", json={"is_seed": False})
    assert resp.status_code == 200
    assert resp.json()["is_seed"] is False


@pytest.mark.asyncio
async def test_claim_request_created(client, seed_card, db_session):
    from app.models.claim_request import ClaimRequest

    resp = await client.post(
        f"/api/v1/cards/{seed_card.id}/claim-requests",
        json={"email": "createur@example.org", "channel_url": "https://youtube.com/@createur"},
    )
    assert resp.status_code == 201
    req = await db_session.scalar(select(ClaimRequest))
    assert req.card_id == seed_card.id
    assert req.status == "pending"


@pytest.mark.asyncio
async def test_claim_rejected_on_non_seed_card(client, seed_card, db_session):
    seed_card.is_seed = False
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/cards/{seed_card.id}/claim-requests",
        json={"email": "x@example.org", "channel_url": "https://youtube.com/@x"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_claim_404_on_unknown_card(client):
    resp = await client.post(
        f"/api/v1/cards/{uuid4()}/claim-requests",
        json={"email": "x@example.org", "channel_url": "https://youtube.com/@x"},
    )
    assert resp.status_code == 404
