from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BIB = b"@article{a1, title={Test}, doi={10.1234/x.1}, year={2023}, author={Doe, Jane}}"


@pytest_asyncio.fixture
async def client(db_session, test_user):
    from app.api.v1.endpoints.cards import get_current_user
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
async def anon_client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_parse_requires_auth(anon_client):
    resp = await anon_client.post(
        "/api/v1/import/parse", files={"file": ("refs.bib", BIB, "text/plain")}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_parse_bibtex(client):
    resp = await client.post(
        "/api/v1/import/parse", files={"file": ("refs.bib", BIB, "text/plain")}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["format_detected"] == "bibtex"
    assert body["skipped"] == 0
    assert len(body["sources"]) == 1
    src = body["sources"][0]
    assert src["url"] == "https://doi.org/10.1234/x.1"
    assert src["title"] == "Test"
    assert src["published_at"] == "2023-01-01T00:00:00Z"
    assert src["category"] == "article-scientifique"
    assert src["author_kind"] == "chercheur"
    assert src["format"] == "texte"


@pytest.mark.asyncio
async def test_import_parse_unknown_format_422(client):
    resp = await client.post(
        "/api/v1/import/parse?format=docx",
        files={"file": ("refs.docx", b"x", "text/plain")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_parse_file_too_large_413(client):
    big = b"a" * (5 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/import/parse", files={"file": ("big.md", big, "text/plain")}
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_paste_deterministic_without_llm(client, monkeypatch):
    async def no_llm(text):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    resp = await client.post(
        "/api/v1/import/paste",
        json={"text": "Voir https://example.org/article et doi 10.1234/x.9"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["format_detected"] == "texte-libre"
    urls = [s["url"] for s in body["sources"]]
    assert "https://example.org/article" in urls
    assert "https://doi.org/10.1234/x.9" in urls


@pytest.mark.asyncio
async def test_import_paste_llm_enriches_and_adds(client, monkeypatch):
    from app.schemas.source import SourceCategory
    from app.services.llm import LlmBiblioRef

    async def fake_llm(text):
        return [
            # Enrichit une URL déjà captée par le déterministe
            LlmBiblioRef(
                url="https://example.org/article",
                title="Titre LLM",
                authors="Dupont, Marie",
                year=2022,
                category=SourceCategory.ARTICLE_PRESSE,
            ),
            # Ajoute une ref DOI absente du texte brut
            LlmBiblioRef(doi="10.9999/nouveau.1", title="Nouveau papier"),
            # Sans lien → skipped
            LlmBiblioRef(title="Ref sans lien"),
        ]

    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", fake_llm)
    resp = await client.post(
        "/api/v1/import/paste", json={"text": "Voir https://example.org/article"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] == 1
    by_url = {s["url"]: s for s in body["sources"]}
    enriched = by_url["https://example.org/article"]
    assert enriched["title"] == "Titre LLM"
    assert enriched["authors"] == "Dupont, Marie"
    assert enriched["category"] == "article-presse"
    assert by_url["https://doi.org/10.9999/nouveau.1"]["title"] == "Nouveau papier"


@pytest.mark.asyncio
async def test_import_paste_requires_auth(anon_client):
    resp = await anon_client.post("/api/v1/import/paste", json={"text": "x"})
    assert resp.status_code == 401


# --- from-content-url ------------------------------------------------------

FAKE_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta property="og:title" content="A Neural Network Framework for Cognitive Bias">
  <meta property="og:description" content="Cognitive biases arise from...">
</head>
<body>
  <article>Main content of the article.</article>
  <section id="references">
    <h2>References</h2>
    <ol>
      <li>Kahneman D. (2011). Thinking, Fast and Slow. https://doi.org/10.1234/foo.1</li>
      <li>Tversky A., Kahneman D. (1974). Judgment under uncertainty.
          https://www.example.org/tversky1974</li>
    </ol>
  </section>
</body>
</html>"""


@pytest.mark.asyncio
async def test_import_from_content_url_requires_auth(anon_client):
    resp = await anon_client.post(
        "/api/v1/import/from-content-url",
        json={"url": "https://example.org/article"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_from_content_url_rejects_unsafe(client):
    resp = await client.post(
        "/api/v1/import/from-content-url",
        json={"url": "http://127.0.0.1:8000/health"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unsafe_url"


@pytest.mark.asyncio
async def test_import_from_content_url_extracts_references(client, monkeypatch):
    """Sur une page HTML avec section References, retourne titre + refs."""
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_meta(url):
        return ExtractedMetadata(
            title="A Neural Network Framework for Cognitive Bias",
            description="Cognitive biases arise from...",
            authors="Korteling J., Brouwer A., Toet A.",
        )

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = FAKE_ARTICLE_HTML

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url):
            return FakeResponse()

    async def no_llm(text):
        return None  # regex-only path suffit pour ce test

    monkeypatch.setattr("app.api.v1.endpoints.imports.extract_url_metadata", fake_meta)
    monkeypatch.setattr("app.api.v1.endpoints.imports.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    # SSRF bypass sur le domaine de test.
    monkeypatch.setattr("app.api.v1.endpoints.imports.assert_url_is_safe", lambda u: None)

    resp = await client.post(
        "/api/v1/import/from-content-url",
        json={"url": "https://www.frontiersin.org/articles/10.3389/fpsyg.2018.01561/full"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["card"]["title"] == "A Neural Network Framework for Cognitive Bias"
    assert body["card"]["content_url"].endswith("/full")
    assert body["references_section_found"] is True
    urls = {s["url"] for s in body["sources"]}
    assert "https://doi.org/10.1234/foo.1" in urls
    assert "https://www.example.org/tversky1974" in urls
