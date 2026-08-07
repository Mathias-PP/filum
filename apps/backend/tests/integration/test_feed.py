"""Feed chronologique public : registre, jamais fil algorithmique.

Contrat verifie :
- publier une fiche publique cree une entree ;
- une fiche privee n'apparait jamais ;
- l'ordre est strictement anti-chronologique ;
- pas de compteurs d'engagement dans la reponse ;
- pagination par curseur, jamais par offset.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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


async def _publish_card(db_session, user, *, slug, title, at, visibility="public"):
    from app.models.biblio_card import BiblioCard
    from app.models.feed_event import FeedEvent, FeedEventKind

    card = BiblioCard(
        id=uuid4(),
        user_id=user.id,
        slug=slug,
        title=title,
        content_type="article",
        platform="blog",
        status="published",
        visibility=visibility,
        published_at=at,
    )
    db_session.add(card)
    if visibility == "public":
        db_session.add(
            FeedEvent(
                kind=FeedEventKind.CARD_PUBLISHED,
                actor_id=user.id,
                card_id=card.id,
                occurred_at=at,
            )
        )
    await db_session.commit()
    return card


@pytest.mark.asyncio
async def test_feed_returns_public_cards_in_reverse_chronological_order(
    client, db_session, test_user
):
    await _publish_card(
        db_session, test_user, slug="ancienne", title="Ancienne fiche",
        at=datetime(2026, 1, 1),
    )
    await _publish_card(
        db_session, test_user, slug="recente", title="Recente fiche",
        at=datetime(2026, 8, 1),
    )
    await _publish_card(
        db_session, test_user, slug="privee", title="Privee",
        at=datetime(2026, 6, 1), visibility="private",
    )

    resp = await client.get("/api/v1/feed")
    assert resp.status_code == 200
    body = resp.json()
    titles = [e["card_title"] for e in body["entries"]]
    assert titles == ["Recente fiche", "Ancienne fiche"]
    # Aucune fiche privee ne fuit :
    assert not any("Privee" in t for t in titles)
    # Aucun compteur d'engagement n'est expose :
    entry = body["entries"][0]
    for banned in ("likes", "views", "score", "engagement", "popularity"):
        assert banned not in entry


@pytest.mark.asyncio
async def test_feed_cursor_pagination(client, db_session, test_user):
    for i in range(5):
        await _publish_card(
            db_session, test_user,
            slug=f"card-{i}", title=f"Fiche {i}",
            at=datetime(2026, 1, 1) + timedelta(days=i),
        )
    resp = await client.get("/api/v1/feed?limit=2")
    body = resp.json()
    assert len(body["entries"]) == 2
    assert body["next_before"] is not None
    # Page suivante : les entrees strictement anterieures au curseur.
    resp2 = await client.get(f"/api/v1/feed?limit=2&before={body['next_before']}")
    body2 = resp2.json()
    titles = [e["card_title"] for e in body2["entries"]]
    assert titles == ["Fiche 2", "Fiche 1"]


@pytest.mark.asyncio
async def test_publish_card_creates_feed_event(db_session, test_user):
    """Le service publish_card doit inserer une entree pour une fiche publique
    et n'en inserer aucune pour une fiche privee (ni pour une republication)."""
    from app.models.biblio_card import BiblioCard
    from app.models.feed_event import FeedEvent
    from app.services.card import CardService
    from sqlalchemy import func, select

    service = CardService(db_session)

    def _card(**overrides):
        return BiblioCard(
            id=uuid4(),
            user_id=test_user.id,
            slug=overrides.get("slug", f"c-{uuid4().hex[:6]}"),
            title="T",
            content_type="article",
            platform="blog",
            status="draft",
            visibility=overrides.get("visibility", "public"),
        )

    public_card = _card(slug="public-one")
    db_session.add(public_card)
    await db_session.commit()
    await db_session.refresh(public_card, ["user"])
    await service.publish_card(public_card)

    private_card = _card(slug="private-one", visibility="private")
    db_session.add(private_card)
    await db_session.commit()
    await db_session.refresh(private_card, ["user"])
    await service.publish_card(private_card)

    # Republier la fiche publique ne cree pas de doublon.
    await service.publish_card(public_card)

    total = await db_session.scalar(select(func.count()).select_from(FeedEvent))
    assert total == 1
