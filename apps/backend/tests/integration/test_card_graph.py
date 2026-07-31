"""Meta-graphe : fiches reliees entre elles par leurs sources.

Contrat produit :
- GET /@{creator}/{card}/graph renvoie la fiche, ses sources, et les fiches
  Philum que ces sources referencent, en BFS borne en profondeur.
- include_sources=false renvoie le graphe fiches-seules (constellation).
- Le parcours ne traverse JAMAIS une fiche non publiee ou non publique :
  l'endpoint est public, il ne doit pas reveler l'existence d'un brouillon.
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


def _card(user_id, slug, title, *, status="published", visibility="public"):
    from app.models.biblio_card import BiblioCard

    return BiblioCard(
        id=uuid4(),
        user_id=user_id,
        slug=slug,
        title=title,
        content_type="article",
        platform="blog",
        status=status,
        visibility=visibility,
    )


def _source(card_id, url, title, *, position=0, linked_card_id=None, authors=None):
    from app.models.source import Source

    return Source(
        id=uuid4(),
        biblio_card_id=card_id,
        position=position,
        url=url,
        title=title,
        format="article",
        category="scientific-article",
        author_kind="researcher",
        linked_card_id=linked_card_id,
        authors=authors,
    )


@pytest_asyncio.fixture
async def chain(db_session, test_user):
    """A -> (source liee) -> B -> (source liee) -> C, plus une fiche privee.

    A cite deux sources dont une pointe vers B. B cite une source pointant
    vers C, et une source pointant vers une fiche privee (jamais traversable).
    """
    a = _card(test_user.id, "fiche-a", "Fiche A")
    b = _card(test_user.id, "fiche-b", "Fiche B")
    c = _card(test_user.id, "fiche-c", "Fiche C")
    secret = _card(test_user.id, "fiche-secrete", "Fiche secrete", visibility="private")
    db_session.add_all([a, b, c, secret])
    await db_session.commit()

    db_session.add_all(
        [
            _source(a.id, "https://example.org/x", "Source ordinaire de A", position=0),
            _source(
                a.id,
                "http://test/@testuser/fiche-b",
                "Fiche B",
                position=1,
                linked_card_id=b.id,
                authors="Doe, J.; Roe, R.",
            ),
            _source(
                b.id, "http://test/@testuser/fiche-c", "Fiche C", position=0, linked_card_id=c.id
            ),
            _source(
                b.id,
                "http://test/@testuser/fiche-secrete",
                "Fiche secrete",
                position=1,
                linked_card_id=secret.id,
            ),
            _source(c.id, "https://example.org/z", "Source ordinaire de C", position=0),
        ]
    )
    await db_session.commit()
    return {"a": a, "b": b, "c": c, "secret": secret}


def _ids(payload, kind):
    return {n["id"] for n in payload["nodes"] if n["kind"] == kind}


@pytest.mark.asyncio
async def test_depth_zero_returns_only_root_card_and_its_sources(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=0")
    assert r.status_code == 200
    data = r.json()
    assert data["root_id"] == f"card:{chain['a'].id}"
    assert _ids(data, "card") == {f"card:{chain['a'].id}"}
    assert len(_ids(data, "source")) == 2
    # Sans profondeur, aucune arete vers une autre fiche.
    assert all(e["kind"] == "cites" for e in data["edges"])


@pytest.mark.asyncio
async def test_depth_one_reveals_the_linked_card(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=1")
    data = r.json()
    assert _ids(data, "card") == {f"card:{chain['a'].id}", f"card:{chain['b'].id}"}
    # L'arete relie les deux fiches directement : c'est ce qui rend le depliage
    # possible cote client.
    assert any(
        e["kind"] == "is_card"
        and e["source"] == f"card:{chain['a'].id}"
        and e["target"] == f"card:{chain['b'].id}"
        for e in data["edges"]
    )


@pytest.mark.asyncio
async def test_a_source_that_designates_a_card_is_not_also_a_source_node(client, chain):
    """Sinon le meme contenu apparait deux fois, en chaine : source puis fiche.

    Cette redondance est la premiere cause de confusion signalee sur le
    meta-graphe : on croit voir deux references distinctes.
    """
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=1")
    data = r.json()
    assert _ids(data, "source") == {
        n["id"] for n in data["nodes"] if n["title"] == "Source ordinaire de A"
    }
    assert not any(n["title"] == "Fiche B" and n["kind"] == "source" for n in data["nodes"])
    # Aucune arete ne part d'un noeud source vers une fiche.
    sources = _ids(data, "source")
    assert not any(e["source"] in sources for e in data["edges"])


@pytest.mark.asyncio
async def test_card_node_carries_the_real_authors_of_the_described_content(client, chain):
    """La fiche ne connait pas ses auteurs : c'est la source qui la designe
    dans la bibliographie de qui la cite qui les porte. Sans cette remontee,
    le graphe n'a que le nom du createur Philum a afficher, ce qui trompe le
    lecteur quand la fiche n'est pas revendiquee."""
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=1")
    node = next(n for n in r.json()["nodes"] if n["id"] == f"card:{chain['b'].id}")
    assert node["authors"] == "Doe, J.; Roe, R."


@pytest.mark.asyncio
async def test_card_node_exposes_is_seed(client, chain, db_session):
    chain["b"].is_seed = True
    await db_session.commit()
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=1")
    nodes = {n["id"]: n for n in r.json()["nodes"]}
    assert nodes[f"card:{chain['b'].id}"]["is_seed"] is True
    assert nodes[f"card:{chain['a'].id}"]["is_seed"] is False


@pytest.mark.asyncio
async def test_depth_two_reaches_the_third_card(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=2")
    data = r.json()
    assert f"card:{chain['c'].id}" in _ids(data, "card")


@pytest.mark.asyncio
async def test_private_card_is_never_traversed(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=3")
    data = r.json()
    assert f"card:{chain['secret'].id}" not in _ids(data, "card")
    # La source qui la vise reste visible en tant que source, sans arete de fiche.
    assert not any(e["target"] == f"card:{chain['secret'].id}" for e in data["edges"])


@pytest.mark.asyncio
async def test_card_nodes_carry_navigation_metadata(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=1")
    node = next(n for n in r.json()["nodes"] if n["id"] == f"card:{chain['b'].id}")
    # Sans slug ni creator_slug le frontend ne peut ni etiqueter ni naviguer.
    assert node["slug"] == "fiche-b"
    assert node["creator_slug"] == "testuser"
    assert node["title"] == "Fiche B"
    assert node["sources_count"] == 2
    assert node["depth"] == 1


@pytest.mark.asyncio
async def test_constellation_mode_returns_cards_only(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=2&include_sources=false")
    data = r.json()
    assert _ids(data, "source") == set()
    assert len(_ids(data, "card")) == 3
    # Les aretes deviennent directes fiche -> fiche.
    assert all(e["kind"] == "is_card" for e in data["edges"])
    assert {(e["source"], e["target"]) for e in data["edges"]} == {
        (f"card:{chain['a'].id}", f"card:{chain['b'].id}"),
        (f"card:{chain['b'].id}", f"card:{chain['c'].id}"),
    }


@pytest.mark.asyncio
async def test_mutual_citation_cycle_terminates(client, db_session, test_user):
    """Deux fiches qui se citent mutuellement : legitime, ne doit pas boucler."""
    x = _card(test_user.id, "fiche-x", "Fiche X")
    y = _card(test_user.id, "fiche-y", "Fiche Y")
    db_session.add_all([x, y])
    await db_session.commit()
    db_session.add_all(
        [
            _source(x.id, "http://test/@testuser/fiche-y", "Y", linked_card_id=y.id),
            _source(y.id, "http://test/@testuser/fiche-x", "X", linked_card_id=x.id),
        ]
    )
    await db_session.commit()

    r = await client.get("/api/v1/@testuser/fiche-x/graph?depth=3")
    assert r.status_code == 200
    data = r.json()
    assert len(_ids(data, "card")) == 2
    # Chaque fiche n'apparait qu'une fois malgre le cycle.
    assert len(data["nodes"]) == len({n["id"] for n in data["nodes"]})


@pytest_asyncio.fixture
async def cited_pair(db_session, test_user):
    """Une fiche publique en cite une autre : seul le lien entrant existe."""
    cited = _card(test_user.id, "fiche-citee", "Fiche citee")
    citing = _card(test_user.id, "fiche-citante", "Fiche citante")
    hidden = _card(test_user.id, "fiche-cachee", "Fiche cachee", visibility="private")
    db_session.add_all([cited, citing, hidden])
    await db_session.commit()
    db_session.add_all(
        [
            _source(
                citing.id, "http://test/@testuser/fiche-citee", "Citee", linked_card_id=cited.id
            ),
            _source(
                hidden.id, "http://test/@testuser/fiche-citee", "Citee", linked_card_id=cited.id
            ),
        ]
    )
    await db_session.commit()
    return {"cited": cited, "citing": citing, "hidden": hidden}


@pytest.mark.asyncio
async def test_constellation_surfaces_incoming_citations(client, cited_pair):
    """« Ou se situe cette fiche » se repond mal en ignorant qui la cite."""
    r = await client.get("/api/v1/@testuser/fiche-citee/graph?depth=1&include_sources=false")
    data = r.json()
    assert _ids(data, "card") == {
        f"card:{cited_pair['cited'].id}",
        f"card:{cited_pair['citing'].id}",
    }
    assert {(e["source"], e["target"]) for e in data["edges"]} == {
        (f"card:{cited_pair['citing'].id}", f"card:{cited_pair['cited'].id}")
    }


@pytest.mark.asyncio
async def test_constellation_never_reveals_a_private_citing_card(client, cited_pair):
    r = await client.get("/api/v1/@testuser/fiche-citee/graph?depth=3&include_sources=false")
    data = r.json()
    assert f"card:{cited_pair['hidden'].id}" not in _ids(data, "card")
    assert all(
        f"card:{cited_pair['hidden'].id}" not in (e["source"], e["target"]) for e in data["edges"]
    )


@pytest.mark.asyncio
async def test_source_graph_stays_outgoing_only(client, cited_pair):
    """Le graphe des sources repond « sur quoi s'appuie-t-elle » : pas d'entrant."""
    r = await client.get("/api/v1/@testuser/fiche-citee/graph?depth=2")
    assert _ids(r.json(), "card") == {f"card:{cited_pair['cited'].id}"}


@pytest.mark.asyncio
async def test_constellation_emits_a_mutual_citation_once_in_each_direction(
    client, db_session, test_user
):
    x = _card(test_user.id, "etoile-x", "Etoile X")
    y = _card(test_user.id, "etoile-y", "Etoile Y")
    db_session.add_all([x, y])
    await db_session.commit()
    db_session.add_all(
        [
            _source(x.id, "http://test/@testuser/etoile-y", "Y", linked_card_id=y.id),
            _source(y.id, "http://test/@testuser/etoile-x", "X", linked_card_id=x.id),
        ]
    )
    await db_session.commit()

    r = await client.get("/api/v1/@testuser/etoile-x/graph?depth=2&include_sources=false")
    edges = [(e["source"], e["target"]) for e in r.json()["edges"]]
    assert len(edges) == len(set(edges))
    assert set(edges) == {
        (f"card:{x.id}", f"card:{y.id}"),
        (f"card:{y.id}", f"card:{x.id}"),
    }


@pytest.mark.asyncio
async def test_unknown_card_returns_404(client):
    r = await client.get("/api/v1/@testuser/inexistante/graph")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_depth_is_capped(client, chain):
    r = await client.get("/api/v1/@testuser/fiche-a/graph?depth=99")
    assert r.status_code == 422
