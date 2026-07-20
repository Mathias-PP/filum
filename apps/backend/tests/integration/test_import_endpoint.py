from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BIB = b"@article{a1, title={Test}, doi={10.1234/x.1}, year={2023}, author={Doe, Jane}}"


@pytest.fixture(autouse=True)
def disable_crossref_backfill_by_default(monkeypatch):
    """Neutralise Crossref pour tous les tests par defaut.

    Sans ca, chaque endpoint d'import (parse/paste/from-content-url) appelle
    Crossref sur chaque ref -> timeouts + variabilite reseau en CI. Les tests
    qui veulent exercer le backfill overrident explicitement.
    """

    async def _no_crossref(doi):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.crossref_lookup", _no_crossref)


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
    assert body["fetch_status"] == "ok"
    urls = {s["url"] for s in body["sources"]}
    assert "https://doi.org/10.1234/foo.1" in urls
    assert "https://www.example.org/tversky1974" in urls


@pytest.mark.asyncio
async def test_import_from_content_url_fetch_status_not_html(client, monkeypatch):
    """PDF/image/JSON → fetch_status='not_html', pas de sources."""
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_meta(url):
        return ExtractedMetadata(title="PDF Article")

    class FakePdfResponse:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        text = ""

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url):
            return FakePdfResponse()

    async def no_llm(text):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.extract_url_metadata", fake_meta)
    monkeypatch.setattr("app.api.v1.endpoints.imports.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    monkeypatch.setattr("app.api.v1.endpoints.imports.assert_url_is_safe", lambda u: None)

    resp = await client.post(
        "/api/v1/import/from-content-url",
        json={"url": "https://example.org/paper.pdf"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fetch_status"] == "not_html"
    assert body["sources"] == []
    assert body["references_section_found"] is False


@pytest.mark.asyncio
async def test_import_from_content_url_fetch_status_unreachable(client, monkeypatch):
    """httpx exception (timeout, DNS) → fetch_status='unreachable'."""
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_meta(url):
        return ExtractedMetadata()  # extract_url_metadata peut aussi failer, ok

    class BrokenAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url):
            raise RuntimeError("connection refused")

    async def no_llm(text):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.extract_url_metadata", fake_meta)
    monkeypatch.setattr("app.api.v1.endpoints.imports.httpx.AsyncClient", BrokenAsyncClient)
    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    monkeypatch.setattr("app.api.v1.endpoints.imports.assert_url_is_safe", lambda u: None)

    resp = await client.post(
        "/api/v1/import/from-content-url",
        json={"url": "https://down.example.org/article"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fetch_status"] == "unreachable"
    assert body["sources"] == []


# --- Crossref backfill -----------------------------------------------------

FRONTIERS_LIKE_HTML = """<!DOCTYPE html>
<html>
<head><meta property="og:title" content="Inhibitory control"></head>
<body>
  <section id="references">
    <h2>References</h2>
    <ol>
      <li>AdlemanN. E.MenonV.BlaseyC. M.WhiteC. D. (2002). A developmental fMRI study of the Stroop color-word task.Neuroimage1661-75. 10.1006/nimg.2001.1046</li>
      <li>AronA. R.RobbinsT. W.PoldrackR. A. (2014). Inhibition and the right inferior frontal cortex: one decade on.Trends in cognitive sciences, 18177-185. 10.1016/j.tics.2013.12.003</li>
      <li>BariA.RobbinsT. W. (2013). Inhibition and impulsivity: behavioral and neural basis of response control.Prog. Neurobiol.10844-79. 10.1016/j.pneurobio.2013.06.005</li>
    </ol>
  </section>
</body>
</html>"""


@pytest.mark.asyncio
async def test_import_from_content_url_backfills_crossref(client, monkeypatch):
    """Cas Frontiers : LLM off, regex trouve juste les DOIs bruts →
    Crossref remplit title/authors/year/category."""
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_meta(url):
        return ExtractedMetadata(title="Inhibitory control")

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = FRONTIERS_LIKE_HTML

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
        return None  # simule LLM disabled / echec sur texte Frontiers bruite

    # Simule Crossref : renvoie metadata pour chaque DOI connu
    _CROSSREF_DB = {
        "10.1006/nimg.2001.1046": ExtractedMetadata(
            title="A developmental fMRI study of the Stroop color-word task",
            authors="Adleman N., Menon V., Blasey C., White C.",
            published_at="2002-11-01",
        ),
        "10.1016/j.tics.2013.12.003": ExtractedMetadata(
            title="Inhibition and the right inferior frontal cortex: one decade on",
            authors="Aron A., Robbins T., Poldrack R.",
            published_at="2014-04-01",
        ),
        "10.1016/j.pneurobio.2013.06.005": ExtractedMetadata(
            title="Inhibition and impulsivity: behavioral and neural basis",
            authors="Bari A., Robbins T.",
            published_at="2013-09-01",
        ),
    }

    async def fake_crossref(doi):
        return _CROSSREF_DB.get(doi.lower())

    monkeypatch.setattr("app.api.v1.endpoints.imports.extract_url_metadata", fake_meta)
    monkeypatch.setattr("app.api.v1.endpoints.imports.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    monkeypatch.setattr("app.api.v1.endpoints.imports.crossref_lookup", fake_crossref)
    monkeypatch.setattr("app.api.v1.endpoints.imports.assert_url_is_safe", lambda u: None)

    resp = await client.post(
        "/api/v1/import/from-content-url",
        json={"url": "https://www.frontiersin.org/articles/10.3389/fpsyg.2022.651547/full"},
    )
    assert resp.status_code == 200
    body = resp.json()
    by_url = {s["url"]: s for s in body["sources"]}
    # Les 3 DOIs ont ete extraits ET enrichis via Crossref
    src1 = by_url["https://doi.org/10.1006/nimg.2001.1046"]
    assert src1["title"] and "Stroop" in src1["title"]
    assert src1["authors"] and "Adleman" in src1["authors"]
    assert src1["published_at"] and src1["published_at"].startswith("2002-")
    assert src1["category"] == "article-scientifique"
    src2 = by_url["https://doi.org/10.1016/j.tics.2013.12.003"]
    assert "decade" in src2["title"]
    assert "Aron" in src2["authors"]


@pytest.mark.asyncio
async def test_import_paste_backfills_crossref_when_llm_off(client, monkeypatch):
    """Le pipeline /import/paste enrichit aussi via Crossref quand le LLM
    est off et que le texte ne contient que des DOIs nus."""
    from app.extractors.url_extractor import ExtractedMetadata

    async def no_llm(text):
        return None

    async def fake_crossref(doi):
        if doi.lower() == "10.1234/x.9":
            return ExtractedMetadata(
                title="Some paper",
                authors="Doe J., Roe M.",
                published_at="2020-05-15",
            )
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.parse_bibliography", no_llm)
    monkeypatch.setattr("app.api.v1.endpoints.imports.crossref_lookup", fake_crossref)

    resp = await client.post(
        "/api/v1/import/paste",
        json={"text": "Voir doi 10.1234/x.9 pour details."},
    )
    assert resp.status_code == 200
    body = resp.json()
    src = next(s for s in body["sources"] if "10.1234/x.9" in s["url"])
    assert src["title"] == "Some paper"
    assert src["authors"] == "Doe J., Roe M."
    # ImportedRef ne garde que l'annee (comme BibTeX/CSL) : jour/mois du
    # published_at Crossref sont perdus lors de la conversion en draft.
    # Amelioration eventuelle future = etendre ImportedRef avec published_at full.
    assert src["published_at"] == "2020-01-01T00:00:00Z"
    assert src["category"] == "article-scientifique"


@pytest.mark.asyncio
async def test_backfill_skips_refs_already_complete(client, monkeypatch):
    """BibTeX complet (title+authors+year deja presents) -> pas de call Crossref."""
    call_count = {"n": 0}

    async def counting_crossref(doi):
        call_count["n"] += 1
        return None

    monkeypatch.setattr("app.api.v1.endpoints.imports.crossref_lookup", counting_crossref)

    resp = await client.post(
        "/api/v1/import/parse", files={"file": ("refs.bib", BIB, "text/plain")}
    )
    assert resp.status_code == 200
    # BibTeX de test a title=Test, author=Doe Jane, year=2023 -> complet -> skip
    assert call_count["n"] == 0
