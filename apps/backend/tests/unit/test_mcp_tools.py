from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def published_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="memoire-cerveau",
        title="Memoire et cerveau",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://doi.org/10.1000/exemple",
        title="Etude exemple",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()
    return card, source


@pytest.mark.asyncio
async def test_search_cards_finds_by_title(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="memoire")
    assert len(results) == 1
    assert results[0]["creator"] == test_user.username
    assert results[0]["slug"] == "memoire-cerveau"
    assert "sources" not in results[0]


@pytest.mark.asyncio
async def test_search_cards_ignores_drafts(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards
    from app.models.biblio_card import BiblioCard

    draft = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon",
        title="Memoire brouillon",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(draft)
    await db_session.commit()
    results = await search_cards(db_session, query="memoire")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_card_returns_compact_sources(db_session, published_card, test_user):
    from app.mcp_server.tools import get_card

    card_dict = await get_card(db_session, creator=test_user.username, slug="memoire-cerveau")
    assert card_dict["title"] == "Memoire et cerveau"
    assert len(card_dict["sources"]) == 1
    src = card_dict["sources"][0]
    assert src["url"] == "https://doi.org/10.1000/exemple"
    assert "annotation" not in src


@pytest.mark.asyncio
async def test_get_card_unknown_returns_none(db_session):
    from app.mcp_server.tools import get_card

    assert await get_card(db_session, creator="nobody", slug="nope") is None


@pytest.mark.asyncio
async def test_get_source_detail(db_session, published_card):
    from app.mcp_server.tools import get_source

    _, source = published_card
    detail = await get_source(db_session, source_id=str(source.id))
    assert detail["title"] == "Etude exemple"
    assert detail["category"] == "article-scientifique"


@pytest.mark.asyncio
async def test_find_cards_citing_same_url(db_session, published_card, test_user):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://doi.org/10.1000/exemple")
    assert len(results) == 1
    assert results[0]["slug"] == "memoire-cerveau"
