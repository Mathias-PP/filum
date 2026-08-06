"""Tests de l'API des fiches bibliographiques."""

from __future__ import annotations

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
async def card_id(client, session_token):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-referencement",
            "title": "Fiche de test",
            "platform": "blog",
            "content_type": "article",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_mise_a_jour_du_referencement_d_une_fiche(client, session_token, card_id):
    """Les trois champs de referencement sont modifiables et relus tels quels."""
    client.cookies.set("filum_session", session_token)
    payload = {"format": "video", "category": "documentaire", "author_kind": "individu"}
    resp = await client.patch(f"/api/v1/cards/{card_id}", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "video"
    assert body["category"] == "documentaire"
    assert body["author_kind"] == "individu"


@pytest.mark.asyncio
async def test_referencement_non_declare_reste_null(client, session_token, card_id):
    """Ne rien declarer ne doit pas produire une valeur par defaut inventee."""
    client.cookies.set("filum_session", session_token)
    resp = await client.get(f"/api/v1/cards/{card_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] is None
    assert body["category"] is None
    assert body["author_kind"] is None
