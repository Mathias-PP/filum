from __future__ import annotations

import io
import zipfile
from datetime import datetime
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
async def published_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-export",
        title="Fiche d'export, avec virgule",
        description="Une description",
        content_url="https://youtube.com/watch?v=abc",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    db_session.add_all(
        [
            Source(
                id=uuid4(),
                biblio_card_id=card.id,
                position=0,
                url="https://example.org/paper",
                title="Titre {avec} accolades",
                authors="Dupont, Marie",
                published_at=datetime(2024, 3, 1),
                format="texte",
                category="article-scientifique",
                author_kind="chercheur",
                annotation='Note "importante"',
                is_pivot=True,
            ),
            Source(
                id=uuid4(),
                biblio_card_id=card.id,
                position=1,
                url="https://example.org/video",
                format="video",
                category="documentaire",
                author_kind="media",
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_export_json(client, published_card, test_user):
    resp = await client.get(f"/api/v1/@{test_user.username}/{published_card.slug}/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["philum_export_version"] == 1
    assert data["card"]["title"] == published_card.title
    assert len(data["sources"]) == 2
    assert data["sources"][0]["is_pivot"] is True


@pytest.mark.asyncio
async def test_export_csv_has_bom_and_rows(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "csv"},
    )
    assert resp.status_code == 200
    raw = resp.content.decode("utf-8")
    assert raw.startswith("\ufeff")
    lines = [line for line in raw.lstrip("\ufeff").splitlines() if line]
    assert len(lines) == 3  # header + 2 sources
    assert lines[0].startswith("position,title,authors,url")


@pytest.mark.asyncio
async def test_export_bibtex(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "bibtex"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "@article{" in body  # article-scientifique
    assert "@misc{" in body  # documentaire
    assert "Titre \\{avec\\} accolades" in body
    assert "year = {2024}" in body


@pytest.mark.asyncio
async def test_export_markdown_frontmatter(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "markdown"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("---\n")
    assert "tags:" in body
    assert "## Sources" in body
    assert "[Titre {avec} accolades](https://example.org/paper)" in body


@pytest.mark.asyncio
async def test_export_xlsx_is_valid_zip(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "xlsx"},
    )
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "[Content_Types].xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "Titre {avec} accolades" in sheet
        assert 'r="A3"' in sheet  # 2e source presente


@pytest.mark.asyncio
async def test_export_docx_is_valid_zip(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "docx"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].endswith('.docx"')
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        doc = zf.read("word/document.xml").decode("utf-8")
        assert "Titre {avec} accolades" in doc
        assert "(source pivot)" in doc
        assert "https://example.org/video" in doc


@pytest.mark.asyncio
async def test_export_unknown_format_422(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "odt"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_404_on_draft_card(client, db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon",
        title="Brouillon",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()
    resp = await client.get(f"/api/v1/@{test_user.username}/brouillon/export")
    assert resp.status_code == 404
