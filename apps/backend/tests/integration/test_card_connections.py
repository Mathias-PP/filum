"""Tests des endpoints de gestion des connexions fiche a fiche."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import LinkOrigin, Source, SourceCategory, SourceFormat
from app.models.user import User


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
async def other_user(db_session):
    user = User(
        id=uuid4(),
        email="other@example.com",
        username="other",
        display_name="Other User",
        public_key="o" * 64,
        encrypted_private_key="encrypted_other_key",
        google_id="google_other_456",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_session_token(other_user):
    from app.services.auth import AuthService

    class _FakeDB:
        pass

    return AuthService.__new__(AuthService).create_session(other_user.id)


@pytest_asyncio.fixture
async def card_id(client, session_token):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "ma-fiche",
            "title": "Ma fiche",
            "platform": "blog",
            "content_type": "article",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def target_card(db_session, other_user):
    """Fiche publiee et publique appartenant a l'autre utilisateur."""
    card = BiblioCard(
        id=uuid4(),
        user_id=other_user.id,
        slug="fiche-cible",
        title="Fiche cible",
        content_type=ContentType.ARTICLE.value,
        platform=Platform.BLOG.value,
        status=CardStatus.PUBLISHED.value,
        visibility="public",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest_asyncio.fixture
async def target_card_id(target_card):
    return str(target_card.id)


@pytest_asyncio.fixture
async def source_id(db_session, test_user, card_id, target_card):
    """Source confirmee dans la biblio de l'utilisateur, pointant vers target_card."""
    from datetime import UTC, datetime
    from uuid import UUID

    source = Source(
        id=uuid4(),
        biblio_card_id=UUID(card_id),
        url="https://example.com/article",
        title="Article cible",
        format=SourceFormat.TEXTE.value,
        category=SourceCategory.ARTICLE_SCIENTIFIQUE.value,
        author_kind="individu",
        position=0,
        linked_card_id=target_card.id,
        link_origin=LinkOrigin.MANUEL.value,
        link_confirmed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return str(source.id)


@pytest_asyncio.fixture
async def suggested_source_id(db_session, test_user, card_id, target_card):
    """Source avec suggestion automatique (non confirmee)."""
    from uuid import UUID

    source = Source(
        id=uuid4(),
        biblio_card_id=UUID(card_id),
        url="https://example.com/autre-article",
        title="Autre article",
        format=SourceFormat.TEXTE.value,
        category=SourceCategory.ARTICLE_SCIENTIFIQUE.value,
        author_kind="individu",
        position=1,
        linked_card_id=target_card.id,
        link_origin=LinkOrigin.CONTENU.value,
        link_confirmed_at=None,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return str(source.id)


@pytest.mark.asyncio
async def test_liste_les_connexions_sortantes_et_entrantes(
    client, session_token, card_id, source_id
):
    client.cookies.set("filum_session", session_token)
    resp = await client.get(f"/api/v1/cards/{card_id}/connections")
    assert resp.status_code == 200
    body = resp.json()
    assert "outgoing" in body and "incoming" in body
    for item in body["outgoing"]:
        assert set(item) >= {"source_id", "card_title", "origin", "confirmed", "editable"}


@pytest.mark.asyncio
async def test_confirmer_une_suggestion(
    client, session_token, card_id, suggested_source_id, db_session
):
    client.cookies.set("filum_session", session_token)
    resp = await client.post(f"/api/v1/cards/{card_id}/connections/{suggested_source_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["confirmed"] is True

    from uuid import UUID

    from app.models.source import Source as SourceModel

    source = await db_session.get(SourceModel, UUID(suggested_source_id))
    assert source is not None
    assert source.link_confirmed_at is not None


@pytest.mark.asyncio
async def test_retirer_un_lien_conserve_la_source(
    client, session_token, card_id, source_id, db_session
):
    client.cookies.set("filum_session", session_token)
    resp = await client.delete(f"/api/v1/cards/{card_id}/connections/{source_id}")
    assert resp.status_code == 204

    from uuid import UUID

    from app.models.source import Source as SourceModel

    source = await db_session.get(SourceModel, UUID(source_id))
    assert source is not None
    assert source.deleted_at is None
    assert source.linked_card_id is None


@pytest.mark.asyncio
async def test_on_ne_touche_pas_la_biblio_d_autrui(
    client, session_token, other_user, card_id, source_id, db_session
):
    """Seul le proprietaire de la source peut modifier la connexion."""
    from app.services.auth import AuthService

    other_token = AuthService.__new__(AuthService).create_session(other_user.id)
    client.cookies.set("filum_session", other_token)
    resp = await client.delete(f"/api/v1/cards/{card_id}/connections/{source_id}")
    assert resp.status_code == 403
