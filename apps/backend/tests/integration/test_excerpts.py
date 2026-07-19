from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints.excerpts import verify_quote

PAGE_TEXT = (
    "Introduction. La mémoire à long terme requiert la synthèse de nouvelles "
    "protéines et un remodelage durable des connexions synaptiques. "
    "Par ailleurs, le sommeil joue un rôle actif dans la consolidation."
)


def test_verify_quote_exact():
    m = verify_quote(PAGE_TEXT, "le sommeil joue un rôle actif")
    assert m is not None
    assert PAGE_TEXT[m.start() : m.end()] == "le sommeil joue un rôle actif"


def test_verify_quote_whitespace_tolerant():
    m = verify_quote(PAGE_TEXT, "la synthèse   de\nnouvelles protéines")
    assert m is not None


def test_verify_quote_rejects_hallucination():
    assert verify_quote(PAGE_TEXT, "les neurones miroirs expliquent l'empathie") is None
    assert verify_quote(PAGE_TEXT, "court") is None


@pytest_asyncio.fixture
async def client(db_session, test_user):
    from app.api.v1.endpoints.sources import get_current_user
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    async def override_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def source(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-test",
        title="Fiche test",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.flush()
    src = Source(
        biblio_card_id=card.id,
        position=1,
        url="https://example.org/article",
        title="Un article",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    return src


@pytest.mark.asyncio
async def test_create_and_delete_excerpt(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Une citation importante.", "suggested_by_ai": True},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "Une citation importante."
    assert body["suggested_by_ai"] is True
    assert body["position"] == 1

    resp = await client.delete(f"/api/v1/sources/{source.id}/excerpts/{body['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_unknown_excerpt_404(client, source):
    resp = await client.delete(f"/api/v1/sources/{source.id}/excerpts/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suggest_verifies_quotes(client, source, monkeypatch):
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=PAGE_TEXT)

    async def fake_llm(page_text, context=None):
        return [
            "le sommeil joue un rôle actif dans la consolidation",
            "citation inventée qui n'apparaît nulle part dans le texte",
        ]

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.suggest_excerpts", fake_llm)

    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_enabled"] is True
    assert len(body["suggestions"]) == 1
    s = body["suggestions"][0]
    assert s["text"] == "le sommeil joue un rôle actif dans la consolidation"
    assert s["char_offset"] == PAGE_TEXT.index("le sommeil")
    assert "Par ailleurs" in s["context_before"]


@pytest.mark.asyncio
async def test_suggest_llm_disabled(client, source, monkeypatch):
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=PAGE_TEXT)

    async def no_llm(page_text, context=None):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.suggest_excerpts", no_llm)

    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": [], "page_text_length": len(PAGE_TEXT), "llm_enabled": False}


@pytest.mark.asyncio
async def test_suggest_no_text_422(client, source, monkeypatch):
    async def fake_scrape(url):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 422
