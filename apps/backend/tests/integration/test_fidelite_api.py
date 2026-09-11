"""Le verdict du juge est prive, et la publication le dit quand il manque.

Deux proprietes qui ne se verifient qu'au niveau de l'API : qu'aucune route
publique ne porte le verdict, et qu'une fiche se publie quand meme quand le juge
ne l'a jamais relue, en le signalant.
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


async def _fiche_avec_extrait_annote(client, db_session, *, annote=True):
    resp = await client.post(
        "/api/v1/cards",
        json={"title": "Fiche", "slug": "energie-cellulaire", "card_kind": "sujet"},
    )
    assert resp.status_code == 201, resp.text
    card = resp.json()

    resp = await client.post(
        "/api/v1/sources",
        params={"card_id": card["id"]},
        json={
            "url": "https://exemple.org/etude",
            "title": "Une etude",
            "format": "texte",
            "category": "article-scientifique",
            "author_kind": "chercheur",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    source = resp.json()

    from uuid import UUID

    from app.models.source_excerpt import SourceExcerpt

    extrait = SourceExcerpt(
        source_id=UUID(source["id"]),
        position=0,
        text="Les mitochondries produisent l'ATP.",
        annotated_by_ai=annote,
    )
    db_session.add(extrait)
    await db_session.commit()
    return card, source, extrait


@pytest.mark.asyncio
async def test_le_rapport_de_fidelite_exige_une_authentification(client, db_session):
    from uuid import uuid4

    resp = await client.get(f"/api/v1/cards/{uuid4()}/fidelite")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_le_rapport_liste_les_extraits_et_ce_qui_reste_a_relire(
    client, db_session, session_token
):
    client.cookies.set("filum_session", session_token)
    card, _source, extrait = await _fiche_avec_extrait_annote(client, db_session)

    resp = await client.get(f"/api/v1/cards/{card['id']}/fidelite")
    assert resp.status_code == 200, resp.text
    corps = resp.json()
    assert corps["actif"] is True
    assert corps["cle_configuree"] is False
    assert corps["en_attente"] == 1
    assert len(corps["verdicts"]) == 1
    assert corps["verdicts"][0]["excerpt_id"] == str(extrait.id)
    assert corps["verdicts"][0]["verdict"] is None
    assert "mesure" in corps["avertissement"]


@pytest.mark.asyncio
async def test_un_extrait_saisi_a_la_main_n_est_pas_en_attente(client, db_session, session_token):
    client.cookies.set("filum_session", session_token)
    card, _source, _extrait = await _fiche_avec_extrait_annote(client, db_session, annote=False)

    resp = await client.get(f"/api/v1/cards/{card['id']}/fidelite")
    assert resp.status_code == 200, resp.text
    assert resp.json()["en_attente"] == 0


@pytest.mark.asyncio
async def test_la_fiche_d_un_autre_est_refusee(client, db_session, session_token):
    from uuid import uuid4

    from app.models.user import User

    client.cookies.set("filum_session", session_token)
    card, _source, _extrait = await _fiche_avec_extrait_annote(client, db_session)

    autre = User(
        id=uuid4(),
        email="autre@example.com",
        username="autre",
        public_key="a" * 64,
        encrypted_private_key="chiffre",
    )
    db_session.add(autre)
    await db_session.commit()

    from app.services.auth import AuthService

    client.cookies.set("filum_session", AuthService(db_session).create_session(autre.id))
    resp = await client.get(f"/api/v1/cards/{card['id']}/fidelite")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_aucune_route_publique_ne_porte_le_verdict(client, db_session, session_token):
    """La separation est structurelle : `SourceExcerptResponse` n'a pas le champ."""
    client.cookies.set("filum_session", session_token)
    card, _source, extrait = await _fiche_avec_extrait_annote(client, db_session)
    extrait.fidelity_verdict = "contredit"
    extrait.fidelity_note = "le passage dit l'inverse"
    await db_session.commit()

    resp = await client.post(f"/api/v1/cards/{card['id']}/publish")
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/@testuser/energie-cellulaire")
    assert resp.status_code == 200, resp.text
    assert "fidelity" not in resp.text
    assert "contredit" not in resp.text
    assert "le passage dit l'inverse" not in resp.text


@pytest.mark.asyncio
async def test_la_publication_reussit_et_signale_ce_qui_n_a_pas_ete_relu(
    client, db_session, session_token
):
    client.cookies.set("filum_session", session_token)
    card, _source, _extrait = await _fiche_avec_extrait_annote(client, db_session)

    resp = await client.post(f"/api/v1/cards/{card['id']}/publish")
    assert resp.status_code == 200, resp.text
    corps = resp.json()
    assert corps["status"] == "published"
    assert corps["avertissements"][0]["code"] == "fidelite_en_attente"


@pytest.mark.asyncio
async def test_un_verdict_pose_fait_taire_l_avertissement(client, db_session, session_token):
    client.cookies.set("filum_session", session_token)
    card, _source, extrait = await _fiche_avec_extrait_annote(client, db_session)
    extrait.fidelity_verdict = "soutient"
    await db_session.commit()

    resp = await client.post(f"/api/v1/cards/{card['id']}/publish")
    assert resp.status_code == 200, resp.text
    assert "avertissements" not in resp.json()
