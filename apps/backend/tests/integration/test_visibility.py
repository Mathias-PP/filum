"""Tests de la visibilite (public | private) sur les fiches.

Contrat produit :
- Fiche visibility='public' : comportement historique, visible par tout le monde.
- Fiche visibility='private' : visible uniquement par son owner connecte.
  Reponse 404 (pas 403) aux non-owners pour ne pas leaker l'existence.
- Le profil public d'un user ne liste jamais ses fiches privees.
"""

from __future__ import annotations

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
async def private_card(db_session, test_user):
    """Fiche publiee mais marquee visibility=private."""
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="ma-fiche-privee",
        title="Fiche privee",
        content_type="article",
        platform="blog",
        status="published",
        visibility="private",
    )
    db_session.add(card)
    await db_session.flush()

    # Une source pour que la fiche soit "publiable" cote logique metier.
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://example.org/a",
        title="Une source",
        format="texte",
        category="page-web",
        author_kind="individu",
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_private_card_hidden_from_anonymous(client, private_card, test_user):
    """Anon → 404 (pas 403, pour ne pas leaker l'existence)."""
    resp = await client.get(f"/api/v1/@{test_user.username}/{private_card.slug}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_private_card_hidden_from_other_user(client, db_session, private_card, test_user):
    """User connecte mais pas owner → 404."""
    from app.models.user import User
    from app.services.auth import AuthService

    intruder = User(
        id=uuid4(),
        email="intruder@example.org",
        username="intruder",
        display_name="Intruder",
        public_key="x" * 64,
        encrypted_private_key="enc",
        google_id="google_intruder",
        is_verified=True,
    )
    db_session.add(intruder)
    await db_session.commit()
    token = AuthService(db_session).create_session(intruder.id)

    client.cookies.set("filum_session", token)
    resp = await client.get(f"/api/v1/@{test_user.username}/{private_card.slug}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_private_card_visible_to_owner(client, private_card, session_token, test_user):
    """L'owner connecte peut voir sa propre fiche privee."""
    client.cookies.set("filum_session", session_token)
    resp = await client.get(f"/api/v1/@{test_user.username}/{private_card.slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["visibility"] == "private"


@pytest.mark.asyncio
async def test_private_card_not_in_public_profile(client, private_card, test_user):
    """Le profil public /users/@{slug} ne liste jamais les fiches privees."""
    resp = await client.get(f"/api/v1/users/@{test_user.username}")
    assert resp.status_code == 200
    slugs = {c["slug"] for c in resp.json()["cards"]}
    assert private_card.slug not in slugs


@pytest.mark.asyncio
async def test_create_card_accepts_visibility(client, session_token):
    """POST /cards accepte visibility='private'."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-privee-nouvelle",
            "title": "Nouvelle",
            "platform": "blog",
            "content_type": "article",
            "visibility": "private",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["visibility"] == "private"


@pytest.mark.asyncio
async def test_create_card_defaults_visibility_public(client, session_token):
    """Sans visibility dans le payload, defaut = 'public'."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-defaut",
            "title": "Sans choix visibility",
            "platform": "blog",
            "content_type": "article",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["visibility"] == "public"


@pytest.mark.asyncio
async def test_update_card_can_toggle_visibility(client, session_token):
    """PATCH permet de basculer visibility apres coup."""
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-a-basculer",
            "title": "Test",
            "platform": "blog",
            "content_type": "article",
            "visibility": "public",
        },
    )
    assert resp.status_code == 201
    card_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/cards/{card_id}", json={"visibility": "private"}
    )
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "private"
