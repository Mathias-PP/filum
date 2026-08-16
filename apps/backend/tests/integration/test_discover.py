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


async def _cite(db_session, card, *, title=None, authors=None, position=9, deleted_at=None):
    from app.models.source import Source

    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=card.id,
            position=position,
            url=f"https://example.org/{uuid4().hex[:8]}",
            title=title,
            authors=authors,
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
            deleted_at=deleted_at,
        )
    )
    await db_session.commit()


class TestRechercheDansLaBibliographie:
    """Chercher dans le corpus, c'est chercher dans ce qu'il cite.

    Mesure en production : la fiche vitrine cite « Optogenetic Stimulation of a
    Hippocampal Engram Activates Fear Memory Recall », et « engram » ne
    ramenait rien. L'annuaire ne lisait que les cinq colonnes de la fiche.
    """

    @pytest.mark.asyncio
    async def test_le_titre_d_une_source_est_atteint(self, client, corpus, db_session):
        await _cite(db_session, corpus, title="Optogenetic Stimulation of a Hippocampal Engram")
        resp = await client.get("/api/v1/discover?q=engram")
        assert [c["slug"] for c in resp.json()["results"]] == ["memoire-et-cerveau"]

    @pytest.mark.asyncio
    async def test_l_auteur_d_une_source_est_atteint(self, client, corpus, db_session):
        # Chercher un chercheur cite est la question la plus courante d'un
        # lecteur qui remonte une bibliographie.
        await _cite(db_session, corpus, title="Planting Misinformation", authors="Elizabeth Loftus")
        resp = await client.get("/api/v1/discover?q=loftus")
        assert [c["slug"] for c in resp.json()["results"]] == ["memoire-et-cerveau"]

    @pytest.mark.asyncio
    async def test_une_fiche_citant_deux_fois_reste_une_fiche(self, client, corpus, db_session):
        # Une jointure la ferait apparaitre deux fois, et le total mentirait.
        await _cite(db_session, corpus, title="Engram et memoire", position=10)
        await _cite(db_session, corpus, title="Engram et sommeil", position=11)
        body = (await client.get("/api/v1/discover?q=engram")).json()
        assert body["total"] == 1
        assert len(body["results"]) == 1

    @pytest.mark.asyncio
    async def test_une_source_supprimee_ne_ramene_plus_la_fiche(self, client, corpus, db_session):
        await _cite(db_session, corpus, title="Engram retire", deleted_at=datetime(2026, 8, 1))
        assert (await client.get("/api/v1/discover?q=engram")).json()["total"] == 0

    @pytest.mark.asyncio
    async def test_une_fiche_privee_ne_fuit_pas_par_sa_bibliographie(
        self, client, db_session, test_user
    ):
        privee = await _make_card(
            db_session, test_user, slug="prive-biblio", title="Prive", visibility="private"
        )
        await _cite(db_session, privee, title="Engram confidentiel")
        assert (await client.get("/api/v1/discover?q=engram")).json()["total"] == 0


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
async def test_discover_creators_returns_only_creators_with_public_cards(client, corpus, test_user):
    """Un compte qui n'a rien publie ne doit pas figurer dans l'index."""
    from app.models.user import User

    silent = User(
        id=uuid4(),
        email="silent@example.com",
        username="silent-user",
        display_name="Silent",
        public_key="k",
        encrypted_private_key="ek",
    )
    client.app if False else None  # keep test_user in fixture; silent won't have cards
    from app.db.database import get_db  # noqa: F401

    async for db in _yield_db_from_client(client):
        db.add(silent)
        await db.commit()
        break

    resp = await client.get("/api/v1/discover/creators")
    assert resp.status_code == 200
    body = resp.json()
    slugs = {r["slug"] for r in body["results"]}
    assert test_user.username in slugs
    assert "silent-user" not in slugs
    creator = next(r for r in body["results"] if r["slug"] == test_user.username)
    assert creator["published_cards_count"] == 3
    assert creator["url"].endswith(f"/@{test_user.username}")


@pytest.mark.asyncio
async def test_discover_creators_q_matches_username_display_bio(client, corpus, test_user):
    """La recherche filtre sur username, display_name et bio."""
    resp = await client.get(f"/api/v1/discover/creators?q={test_user.username[:4]}")
    assert resp.status_code == 200
    slugs = {r["slug"] for r in resp.json()["results"]}
    assert test_user.username in slugs


async def _yield_db_from_client(client):
    """Recupere la session db liee au TestClient (override_get_db)."""
    from app.db.database import get_db
    from app.main import app

    override = app.dependency_overrides.get(get_db)
    if override is None:
        return
    gen = override()
    async for db in gen:
        yield db


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
