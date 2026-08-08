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
    assert resp.json() == {
        "suggestions": [],
        "page_text_length": len(PAGE_TEXT),
        "llm_enabled": False,
    }


@pytest.mark.asyncio
async def test_suggest_une_page_illisible_est_un_etat_pas_une_erreur(client, source, monkeypatch):
    """Mesure du 2026-08-08 : cinq URLs sur dix ne rendent aucun texte.

    Le `422` d'origine arretait la fonctionnalite a la porte, alors que la
    personne a le texte sous les yeux et peut le coller. Une reponse vide
    laisse l'ecran basculer sur le mode de collage.
    """

    async def fake_scrape(url):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []
    assert resp.json()["page_text_length"] == 0
    # Et l'etat annonce est celui du serveur, pas un `True` de commodite :
    # sans modele configure, dire l'inverse ferait afficher « aucun passage
    # citable repere » pour une absence de modele.
    assert resp.json()["llm_enabled"] is False


@pytest.mark.asyncio
async def test_chunk_du_texte_colle_ne_touche_pas_au_reseau(client, source, monkeypatch):
    """Le collage est le seul chemin qui marche derriere un anti-crawler."""

    async def fake_scrape(url):  # pragma: no cover - ne doit pas etre appele
        raise AssertionError("le collage ne doit rien aller chercher")

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    texte = (
        "La memoire de travail retient une information brievement. "
        "Elle ne dure que quelques secondes. Baddeley en a propose un modele."
    )
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/chunk",
        json={"text": texte, "unit": "mots", "size": 8},
    )
    assert resp.status_code == 200
    corps = resp.json()
    assert corps["text_source"] == "pasted"
    assert corps["chunks"]
    for c in corps["chunks"]:
        assert c["text"] in texte
        assert corps["text"][c["start"] : c["end"]] == c["text"]


@pytest.mark.asyncio
async def test_chunk_sur_page_illisible_rend_un_decoupage_vide(client, source, monkeypatch):
    async def fake_scrape(url):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/chunk", json={})
    assert resp.status_code == 200
    assert resp.json()["text_source"] == "none"
    assert resp.json()["chunks"] == []


@pytest.mark.asyncio
async def test_un_extrait_peut_porter_un_intitule(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Elle ne dure que quelques secondes.", "title": "Duree de retention"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Duree de retention"


@pytest.mark.asyncio
async def test_un_extrait_sans_intitule_reste_sans_intitule(client, source):
    """Une chaine vide n'est pas un intitule : elle ne doit pas s'enregistrer."""
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Elle ne dure que quelques secondes.", "title": "   "},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] is None
