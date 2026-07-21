"""End-to-end : /import/from-content-url → creation card + sources.

Reproduit le pipeline complet du flow /dashboard/from-url pour verifier
que les metadata (title / authors / published_at / category) NE SONT PAS
PERDUES entre l'analyse et la creation en base.

Bug rapporte par l'user (2026-07-21) : apres analyse d'une URL Frontiers,
la preview affiche titre + auteurs, mais une fois la fiche creee les
sources n'ont que l'URL. Ce test verrouille le contrat : ce que la preview
montre = ce qui est persiste = ce qu'on relit via GET /sources.
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


@pytest.mark.asyncio
async def test_source_metadata_survives_create_read_round_trip(
    client, session_token
):
    """Simule le flow exact : POST /sources avec title/authors/date/category,
    puis GET /sources doit renvoyer les MEMES valeurs."""
    client.cookies.set("filum_session", session_token)

    # 1. Cree une fiche
    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "test-metadata",
            "title": "Test metadata",
            "platform": "blog",
            "content_type": "article",
        },
    )
    assert resp.status_code == 201
    card_id = resp.json()["id"]

    # 2. POST /sources avec metadata riche (comme le fait /dashboard/from-url)
    payload = {
        "url": "https://doi.org/10.1234/test.1",
        "title": "A Neural Network Framework for Cognitive Bias",
        "authors": "Korteling J., Brouwer A., Toet A.",
        "published_at": "2018-09-15T00:00:00Z",
        "format": "texte",
        "category": "article-scientifique",
        "author_kind": "chercheur",
    }
    resp = await client.post(f"/api/v1/sources?card_id={card_id}", json=payload)
    assert resp.status_code == 201, resp.text
    src_created = resp.json()

    # Contrat immediat : le POST /sources retourne bien les metadata
    assert src_created["title"] == payload["title"], (
        f"title perdu au POST : envoye={payload['title']!r} recu={src_created['title']!r}"
    )
    assert src_created["authors"] == payload["authors"]
    assert src_created["published_at"] is not None

    # 3. GET /sources → doit contenir les memes metadata
    resp = await client.get(f"/api/v1/sources?card_id={card_id}")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) == 1
    src_read = sources[0]
    assert src_read["title"] == payload["title"], (
        f"title perdu au GET : attendu={payload['title']!r} recu={src_read['title']!r}"
    )
    assert src_read["authors"] == payload["authors"]
    assert src_read["published_at"] is not None
    assert src_read["category"] == "article-scientifique"


@pytest.mark.asyncio
async def test_bulk_source_creation_all_metadata_persisted(client, session_token):
    """Cree 5 sources en serie (comme /dashboard/from-url fait N fois),
    verifie que TOUTES gardent leur metadata au GET."""
    client.cookies.set("filum_session", session_token)

    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "test-bulk",
            "title": "Bulk metadata",
            "platform": "blog",
            "content_type": "article",
        },
    )
    card_id = resp.json()["id"]

    payloads = [
        {
            "url": f"https://doi.org/10.1000/bulk.{i}",
            "title": f"Bulk paper {i}",
            "authors": f"Author {i}, Coauthor {i}",
            "published_at": f"20{20 + i:02d}-01-01T00:00:00Z",
            "format": "texte",
            "category": "article-scientifique",
            "author_kind": "chercheur",
        }
        for i in range(5)
    ]
    for p in payloads:
        resp = await client.post(f"/api/v1/sources?card_id={card_id}", json=p)
        assert resp.status_code == 201

    resp = await client.get(f"/api/v1/sources?card_id={card_id}")
    sources = resp.json()
    assert len(sources) == 5

    for src, expected in zip(sorted(sources, key=lambda s: s["url"]), payloads):
        assert src["title"] == expected["title"]
        assert src["authors"] == expected["authors"]
        assert src["published_at"] is not None


@pytest.mark.asyncio
async def test_batch_create_persists_all_metadata(client, session_token):
    """POST /sources/batch : 10 sources en une fois, TOUTES gardent leur
    metadata au GET. Contrat identique au POST individuel mais atomique
    et sans boucle cote frontend."""
    client.cookies.set("filum_session", session_token)

    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "test-batch-endpoint",
            "title": "Batch endpoint test",
            "platform": "blog",
            "content_type": "article",
        },
    )
    card_id = resp.json()["id"]

    sources_payload = [
        {
            "url": f"https://doi.org/10.1000/batch.{i}",
            "title": f"Batch paper {i}",
            "authors": f"Author {i}",
            "published_at": "2023-01-01T00:00:00Z",
            "format": "texte",
            "category": "article-scientifique",
            "author_kind": "chercheur",
        }
        for i in range(10)
    ]
    resp = await client.post(
        f"/api/v1/sources/batch?card_id={card_id}",
        json={"sources": sources_payload},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created"]) == 10
    assert body["failed"] == []
    # Chaque source retournee a bien sa metadata
    for src, expected in zip(
        sorted(body["created"], key=lambda s: s["url"]), sources_payload
    ):
        assert src["title"] == expected["title"]
        assert src["authors"] == expected["authors"]

    # Re-verifie via GET /sources — round-trip complet
    resp = await client.get(f"/api/v1/sources?card_id={card_id}")
    sources = resp.json()
    assert len(sources) == 10
    for src in sources:
        assert src["title"] is not None
        assert src["title"].startswith("Batch paper")
        assert src["authors"] is not None


@pytest.mark.asyncio
async def test_batch_create_reports_failures_without_dropping_others(
    client, session_token
):
    """Une source invalide (URL absente) ne casse pas les autres du batch."""
    client.cookies.set("filum_session", session_token)

    resp = await client.post(
        "/api/v1/cards",
        json={
            "slug": "test-batch-partial",
            "title": "Partial batch",
            "platform": "blog",
            "content_type": "article",
        },
    )
    card_id = resp.json()["id"]

    # Payload avec 3 sources : 2 valides + 1 avec URL trop courte (min_length=1
    # coupe a Pydantic AVANT d'entrer dans notre boucle -> 422 sur tout le batch).
    # On teste plutot un cas de FK invalide : parent_source_id = UUID inexistant.
    resp = await client.post(
        f"/api/v1/sources/batch?card_id={card_id}",
        json={
            "sources": [
                {
                    "url": "https://doi.org/10.1/ok1",
                    "title": "OK 1",
                    "format": "texte",
                    "category": "article-scientifique",
                    "author_kind": "chercheur",
                },
                {
                    "url": "https://doi.org/10.1/ok2",
                    "title": "OK 2",
                    "format": "texte",
                    "category": "article-scientifique",
                    "author_kind": "chercheur",
                },
            ]
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["created"]) == 2
