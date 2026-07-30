"""Meta-fiches : picker de fiche liee + garde d'acces.

Contrat produit :
- GET /cards/search propose les fiches de l'utilisateur (meme en brouillon)
  et toutes les fiches publiees ET publiques des autres.
- Une source ne peut designer une fiche que si cette fiche est dans cet
  ensemble : sinon un id devine permettrait de rattacher une source a une
  fiche privee d'autrui, et d'en confirmer l'existence.
- Le lien choisi doit survivre a toute edition ulterieure de la source :
  c'est ce qui manquait, et qui rendait les meta-fiches impossibles.
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


@pytest_asyncio.fixture
async def other_user(db_session):
    from app.models.user import User

    user = User(
        id=uuid4(),
        email="other@example.org",
        username="other",
        display_name="Other",
        public_key="y" * 64,
        encrypted_private_key="enc",
        google_id="google_other",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


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


@pytest_asyncio.fixture
async def cards(db_session, test_user, other_user):
    """Un echantillon couvrant les quatre combinaisons owner x visibilite."""
    made = {
        "own_draft": _card(test_user.id, "mon-brouillon", "Mon brouillon", status="draft"),
        "own_private": _card(test_user.id, "mon-prive", "Mon prive", visibility="private"),
        "other_public": _card(other_user.id, "leur-public", "Leur public"),
        "other_draft": _card(other_user.id, "leur-brouillon", "Leur brouillon", status="draft"),
        "other_private": _card(other_user.id, "leur-prive", "Leur prive", visibility="private"),
    }
    for card in made.values():
        db_session.add(card)
    await db_session.commit()
    return made


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    assert (await client.get("/api/v1/cards/search")).status_code == 401


@pytest.mark.asyncio
async def test_search_scope(client, session_token, cards):
    """Fiches de l'user (tous statuts) + publiees/publiques des autres."""
    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/search", params={"limit": 50})
    assert resp.status_code == 200
    slugs = {c["slug"] for c in resp.json()}
    assert cards["own_draft"].slug in slugs
    assert cards["own_private"].slug in slugs
    assert cards["other_public"].slug in slugs
    assert cards["other_draft"].slug not in slugs
    assert cards["other_private"].slug not in slugs


@pytest.mark.asyncio
async def test_search_filters_on_title(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/search", params={"q": "leur public"})
    assert resp.status_code == 200
    assert [c["slug"] for c in resp.json()] == [cards["other_public"].slug]


@pytest.mark.asyncio
async def test_search_marks_ownership(client, session_token, cards, test_user):
    """is_own permet au picker de signaler les brouillons de l'utilisateur."""
    client.cookies.set("filum_session", session_token)
    resp = await client.get("/api/v1/cards/search", params={"limit": 50})
    by_slug = {c["slug"]: c for c in resp.json()}
    assert by_slug[cards["own_draft"].slug]["is_own"] is True
    assert by_slug[cards["own_draft"].slug]["creator_slug"] == test_user.username
    assert by_slug[cards["other_public"].slug]["is_own"] is False


async def _create_source(client, card_id, linked_card_id):
    return await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json={
            "url": "https://example.org/une-source",
            "title": "Une source",
            "format": "texte",
            "category": "page-web",
            "author_kind": "individu",
            "linked_card_id": str(linked_card_id),
        },
    )


@pytest.mark.asyncio
async def test_source_accepts_own_draft_as_link(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    host = cards["own_private"]
    resp = await _create_source(client, host.id, cards["own_draft"].id)
    assert resp.status_code == 201
    assert resp.json()["linked_card_id"] == str(cards["own_draft"].id)


@pytest.mark.asyncio
async def test_source_accepts_other_public_card_as_link(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    resp = await _create_source(client, cards["own_draft"].id, cards["other_public"].id)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_source_rejects_other_private_card_as_link(client, session_token, cards):
    """404 serait un leak d'existence cote picker ; 400 uniforme."""
    client.cookies.set("filum_session", session_token)
    resp = await _create_source(client, cards["own_draft"].id, cards["other_private"].id)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_linked_card"


@pytest.mark.asyncio
async def test_source_rejects_other_draft_card_as_link(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    resp = await _create_source(client, cards["own_draft"].id, cards["other_draft"].id)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_source_rejects_unknown_card_as_link(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    resp = await _create_source(client, cards["own_draft"].id, uuid4())
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_source_rejects_self_reference(client, session_token, cards):
    """Une fiche parente d'elle-meme creerait un cycle trivial dans le graphe."""
    client.cookies.set("filum_session", session_token)
    host = cards["own_draft"]
    resp = await _create_source(client, host.id, host.id)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_validates_linked_card(client, session_token, cards):
    client.cookies.set("filum_session", session_token)
    created = await _create_source(client, cards["own_draft"].id, cards["own_private"].id)
    source_id = created.json()["id"]

    resp = await client.patch(
        f"/api/v1/sources/{source_id}",
        json={"linked_card_id": str(cards["other_private"].id)},
    )
    assert resp.status_code == 400

    resp = await client.patch(
        f"/api/v1/sources/{source_id}",
        json={"linked_card_id": str(cards["other_public"].id)},
    )
    assert resp.status_code == 200
    assert resp.json()["linked_card_id"] == str(cards["other_public"].id)


@pytest.mark.asyncio
async def test_link_survives_an_unrelated_edit(client, session_token, cards):
    """Le lien etait perdu des qu'on retouchait un autre champ de la source.

    Cause du bug vecu : SourceUpdate ne declarait pas le champ, donc toute
    edition ecrasait le lien sans que rien ne le signale.
    """
    client.cookies.set("filum_session", session_token)
    created = await _create_source(client, cards["own_draft"].id, cards["own_private"].id)
    source_id = created.json()["id"]

    resp = await client.patch(
        f"/api/v1/sources/{source_id}",
        json={"title": "Titre corrige"},
    )
    assert resp.status_code == 200
    assert resp.json()["linked_card_id"] == str(cards["own_private"].id)


@pytest.mark.asyncio
async def test_link_can_be_removed(client, session_token, cards):
    """Le bouton « Retirer » du picker doit vraiment detacher la fiche."""
    client.cookies.set("filum_session", session_token)
    created = await _create_source(client, cards["own_draft"].id, cards["own_private"].id)
    source_id = created.json()["id"]

    resp = await client.patch(f"/api/v1/sources/{source_id}", json={"linked_card_id": None})
    assert resp.status_code == 200
    assert resp.json()["linked_card_id"] is None
