"""Tests de l'annuaire public des fiches (`/api/v1/discover`).

Contrat : une surface anonyme, pour un visiteur humain comme pour une IA.
Elle ne montre que ce qui est publie ET public, filtre sur ce dont on dispose
reellement (createur de la fiche, auteur du contenu, titre, plateforme, dates)
et pagine.
"""

from __future__ import annotations

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


async def _make_card(db_session, user, **kwargs):
    from app.models.biblio_card import BiblioCard

    defaults = {
        "id": uuid4(),
        "user_id": user.id,
        "slug": f"fiche-{uuid4().hex[:8]}",
        "title": "Une fiche",
        "content_type": "article",
        "platform": "blog",
        "status": "published",
        "visibility": "public",
    }
    defaults.update(kwargs)
    card = BiblioCard(**defaults)
    db_session.add(card)
    await db_session.commit()
    return card


@pytest_asyncio.fixture
async def corpus(db_session, test_user):
    """Trois fiches publiques, une privee, un brouillon."""
    from app.models.source import Source

    public_a = await _make_card(
        db_session,
        test_user,
        slug="memoire-et-cerveau",
        title="Memoire et cerveau",
        content_authors="Marie Curie",
        platform="youtube",
        content_type="video",
        published_at=datetime(2026, 1, 15),
    )
    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=public_a.id,
            position=0,
            url="https://doi.org/10.1000/exemple",
            title="Etude exemple",
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
        )
    )
    await _make_card(
        db_session,
        test_user,
        slug="climat-et-oceans",
        title="Climat et oceans",
        content_authors="Jean Jouzel",
        platform="blog",
        content_type="article",
        published_at=datetime(2026, 6, 1),
    )
    await _make_card(
        db_session,
        test_user,
        slug="podcast-abeilles",
        title="Les abeilles",
        platform="podcast",
        content_type="podcast",
        published_at=datetime(2025, 3, 10),
    )
    await _make_card(
        db_session, test_user, slug="dossier-prive", title="Dossier prive", visibility="private"
    )
    await _make_card(db_session, test_user, slug="brouillon", title="Brouillon", status="draft")
    await db_session.commit()
    return public_a


@pytest.mark.asyncio
async def test_discover_is_anonymous(client, corpus):
    """Aucune session : l'annuaire repond quand meme."""
    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["results"]) == 3


@pytest.mark.asyncio
async def test_discover_hides_private_and_draft(client, corpus):
    """Ni les fiches privees ni les brouillons ne fuient par l'annuaire."""
    resp = await client.get("/api/v1/discover")
    slugs = {c["slug"] for c in resp.json()["results"]}
    assert "dossier-prive" not in slugs
    assert "brouillon" not in slugs


@pytest.mark.asyncio
async def test_discover_result_shape(client, corpus, test_user):
    """Une IA doit pouvoir citer sans second appel : URL publique et compte de sources."""
    resp = await client.get("/api/v1/discover?q=memoire")
    results = resp.json()["results"]
    assert len(results) == 1
    r = results[0]
    assert r["slug"] == "memoire-et-cerveau"
    assert r["creator_slug"] == test_user.username
    assert r["content_authors"] == "Marie Curie"
    assert r["source_count"] == 1
    assert r["url"].endswith(f"/@{test_user.username}/memoire-et-cerveau")


@pytest.mark.asyncio
async def test_discover_q_matches_title(client, corpus):
    resp = await client.get("/api/v1/discover?q=oceans")
    assert [c["slug"] for c in resp.json()["results"]] == ["climat-et-oceans"]


@pytest.mark.asyncio
async def test_discover_q_matches_content_author(client, corpus):
    """Chercher « Jouzel » doit trouver la fiche dont il est l'auteur du contenu."""
    resp = await client.get("/api/v1/discover?q=jouzel")
    assert [c["slug"] for c in resp.json()["results"]] == ["climat-et-oceans"]


@pytest.mark.asyncio
async def test_discover_q_matches_creator(client, corpus, test_user):
    """Chercher le nom de l'auteur de la fiche doit ramener toutes ses fiches."""
    resp = await client.get(f"/api/v1/discover?q={test_user.username}")
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_discover_q_escapes_wildcards(client, corpus):
    """« % » est un caractere, pas un joker : sinon la recherche ramene tout."""
    resp = await client.get("/api/v1/discover?q=%25")
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_discover_filter_creator(client, corpus, test_user):
    resp = await client.get(f"/api/v1/discover?creator={test_user.username}")
    assert resp.json()["total"] == 3
    resp = await client.get("/api/v1/discover?creator=personne")
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_discover_filter_platform_and_type(client, corpus):
    resp = await client.get("/api/v1/discover?platform=youtube")
    assert [c["slug"] for c in resp.json()["results"]] == ["memoire-et-cerveau"]
    resp = await client.get("/api/v1/discover?content_type=podcast")
    assert [c["slug"] for c in resp.json()["results"]] == ["podcast-abeilles"]


@pytest.mark.asyncio
async def test_discover_filter_dates(client, corpus):
    resp = await client.get("/api/v1/discover?published_after=2026-01-01")
    assert resp.json()["total"] == 2
    resp = await client.get("/api/v1/discover?published_before=2025-12-31")
    assert [c["slug"] for c in resp.json()["results"]] == ["podcast-abeilles"]


@pytest.mark.asyncio
async def test_discover_sorted_by_recent_by_default(client, corpus):
    slugs = [c["slug"] for c in (await client.get("/api/v1/discover")).json()["results"]]
    assert slugs == ["climat-et-oceans", "memoire-et-cerveau", "podcast-abeilles"]


@pytest.mark.asyncio
async def test_discover_pagination(client, corpus):
    resp = await client.get("/api/v1/discover?limit=2")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["results"]) == 2
    resp = await client.get("/api/v1/discover?limit=2&offset=2")
    assert len(resp.json()["results"]) == 1


@pytest.mark.asyncio
async def test_discover_facets_are_anonymous_and_public_only(client, corpus):
    """Les filtres de l'UI ne doivent proposer que des options qui existent."""
    resp = await client.get("/api/v1/discover/facets")
    assert resp.status_code == 200
    body = resp.json()
    platforms = {f["value"]: f["count"] for f in body["platforms"]}
    assert platforms == {"youtube": 1, "blog": 1, "podcast": 1}
    types = {f["value"]: f["count"] for f in body["content_types"]}
    assert types == {"video": 1, "article": 1, "podcast": 1}
    assert body["total"] == 3
