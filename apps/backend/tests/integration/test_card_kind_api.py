"""La nature d'une fiche tient de bout en bout, de la creation a la publication.

Le schema refuse deja de melanger les deux natures dans un meme corps. Restent
deux regles qui ne se jugent qu'en connaissant la fiche stockee : une fiche
contenu ne se publie pas sans lien vers le contenu qu'elle annonce documenter,
et devenir une fiche sujet efface ce qui decrivait ce contenu.
"""

from __future__ import annotations

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


async def _creer(client, **champs):
    resp = await client.post("/api/v1/cards", json={"title": "Fiche", **champs})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ajouter_une_source(client, card_id):
    resp = await client.post(
        "/api/v1/sources",
        params={"card_id": card_id},
        json={
            "url": "https://exemple.org/etude",
            "title": "Une etude",
            "format": "texte",
            "category": "article-scientifique",
            "author_kind": "chercheur",
        },
    )
    assert resp.status_code in (200, 201), resp.text


@pytest.mark.asyncio
async def test_une_fiche_sujet_se_publie_sans_contenu_source(client, session_token):
    client.cookies.set("filum_session", session_token)
    fiche = await _creer(client, slug="pourquoi-dormir", card_kind="sujet")
    assert fiche["card_kind"] == "sujet"
    assert fiche["platform"] is None
    assert fiche["content_type"] is None

    await _ajouter_une_source(client, fiche["id"])
    resp = await client.post(f"/api/v1/cards/{fiche['id']}/publish")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_une_fiche_contenu_ne_se_publie_pas_sans_lien(client, session_token):
    client.cookies.set("filum_session", session_token)
    fiche = await _creer(client, slug="ma-video", platform="youtube", content_type="video")
    await _ajouter_une_source(client, fiche["id"])

    resp = await client.post(f"/api/v1/cards/{fiche['id']}/publish")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"

    modif = await client.patch(
        f"/api/v1/cards/{fiche['id']}",
        json={"content_url": "https://www.youtube.com/watch?v=demo"},
    )
    assert modif.status_code == 200
    assert (await client.post(f"/api/v1/cards/{fiche['id']}/publish")).status_code == 200


@pytest.mark.asyncio
async def test_devenir_une_fiche_sujet_efface_ce_qui_decrivait_le_contenu(client, session_token):
    client.cookies.set("filum_session", session_token)
    fiche = await _creer(
        client,
        slug="ma-video",
        content_url="https://www.youtube.com/watch?v=demo",
        content_authors="Un vulgarisateur",
        platform="youtube",
        content_type="video",
        is_seed=True,
    )

    resp = await client.patch(f"/api/v1/cards/{fiche['id']}", json={"card_kind": "sujet"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["card_kind"] == "sujet"
    assert body["content_url"] is None
    assert body["content_authors"] is None
    assert body["platform"] is None
    assert body["content_type"] is None
    #: Sans contenu source, il n'y a plus d'auteur tiers a qui reclamer la fiche.
    assert body["is_seed"] is False


@pytest.mark.asyncio
async def test_le_texte_integral_bloque_le_passage_en_fiche_sujet(client, session_token):
    client.cookies.set("filum_session", session_token)
    fiche = await _creer(
        client,
        slug="mon-article",
        content_url="https://exemple.org/mon-article",
        content_text="Le texte integral de l'article.",
    )

    #: Refuser plutot qu'effacer : c'est le seul champ de contenu qui porte un
    #: travail de saisie et ne se reconstitue pas.
    resp = await client.patch(f"/api/v1/cards/{fiche['id']}", json={"card_kind": "sujet"})
    assert resp.status_code == 400
    assert "texte" in resp.json()["error"]["message"]

    ok = await client.patch(
        f"/api/v1/cards/{fiche['id']}", json={"card_kind": "sujet", "content_text": ""}
    )
    assert ok.status_code == 200
    assert ok.json()["content_text"] is None
