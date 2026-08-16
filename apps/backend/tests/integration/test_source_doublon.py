"""Une meme source ne doit pas pouvoir etre ajoutee deux fois a une fiche.

Mesure du 2026-08-16, en peuplant une fiche de 77 references : deux boucles
d'ajout ont tourne en meme temps, et la fiche s'est retrouvee avec 80 sources
pour 77 references distinctes. Aucune des requetes n'a rien signale ; les trois
doublons n'ont ete vus qu'en comparant les DOI un a un, apres coup.

Le cout n'est pas cosmetique. Une reference comptee deux fois gonfle le nombre
de sources, se fait archiver deux fois chez Wayback, se fait enrichir deux fois
chez Crossref et Unpaywall, et apparait deux fois dans le graphe.

Ce qui identifie un doublon : le DOI, ou l'URL une fois normalisee. Pas le
titre : deux chapitres homonymes d'ouvrages differents sont deux sources.
Une source sans DOI ni URL (un livre saisi a la main) n'a pas d'identite
comparable, et reste donc toujours acceptee.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


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


async def _cree_fiche(db_session, test_user, slug: str) -> str:
    #: Creee en base et non par l'endpoint : celui-ci est plafonne a 20 fiches
    #: par heure et par IP, quota partage par toute la suite de tests.
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug=slug,
        title="Fiche de test",
        platform="blog",
        content_type="article",
    )
    db_session.add(card)
    await db_session.flush()
    return str(card.id)


def _source(**kw) -> dict:
    base = {
        "url": "https://doi.org/10.3322/caac.21820",
        "title": "Cancer statistics, 2024",
        "format": "texte",
        "category": "article-scientifique",
        "author_kind": "chercheur",
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_la_meme_url_deux_fois_est_refusee(client, db_session, test_user):
    card_id = await _cree_fiche(db_session, test_user, "doublon-url")

    premier = await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())
    assert premier.status_code == 201, premier.text

    second = await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())

    assert second.status_code == 409, second.text
    detail = second.json()["error"]
    assert detail["code"] == "duplicate_source"
    #: Le message doit designer la source deja presente, sinon l'appelant ne
    #: peut ni la corriger ni la retrouver.
    assert detail["existing_source_id"] == premier.json()["id"]


@pytest.mark.asyncio
async def test_le_meme_doi_sous_une_autre_adresse_est_refuse(client, db_session, test_user):
    #: Le meme article se lit chez l'editeur et sur doi.org. C'est le cas qui a
    #: produit les doublons : deux chemins d'ajout, deux adresses, un article.
    card_id = await _cree_fiche(db_session, test_user, "doublon-doi")

    premier = await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json=_source(url="https://doi.org/10.3322/caac.21820", doi="10.3322/caac.21820"),
    )
    assert premier.status_code == 201, premier.text

    second = await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json=_source(
            url="https://acsjournals.onlinelibrary.wiley.com/doi/10.3322/caac.21820",
            doi="10.3322/CAAC.21820",
        ),
    )

    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "duplicate_source"


@pytest.mark.asyncio
async def test_deux_sources_distinctes_passent_toujours(client, db_session, test_user):
    card_id = await _cree_fiche(db_session, test_user, "sources-distinctes")

    a = await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())
    b = await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json=_source(url="https://doi.org/10.1038/s41467-025-64094-7", title="Real-world data"),
    )

    assert a.status_code == 201
    assert b.status_code == 201, b.text


@pytest.mark.asyncio
async def test_une_source_sans_adresse_reste_toujours_acceptee(client, db_session, test_user):
    #: Livres et chapitres arrivent sans URL ni DOI. Les rapprocher par le
    #: titre seul confondrait deux ouvrages homonymes : on les accepte.
    card_id = await _cree_fiche(db_session, test_user, "sources-sans-adresse")

    a = await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json=_source(url="", title="Molecular Biology of the Cell", category="livre"),
    )
    b = await client.post(
        f"/api/v1/sources?card_id={card_id}",
        json=_source(url="", title="Molecular Biology of the Cell", category="livre"),
    )

    assert a.status_code == 201
    assert b.status_code == 201, b.text


@pytest.mark.asyncio
async def test_la_meme_source_sur_deux_fiches_reste_permise(client, db_session, test_user):
    #: Deux fiches peuvent citer le meme article : le doublon se juge dans une
    #: fiche, jamais entre fiches.
    premiere = await _cree_fiche(db_session, test_user, "premiere-fiche-doublon")
    seconde = await _cree_fiche(db_session, test_user, "seconde-fiche-doublon")

    a = await client.post(f"/api/v1/sources?card_id={premiere}", json=_source())
    b = await client.post(f"/api/v1/sources?card_id={seconde}", json=_source())

    assert a.status_code == 201
    assert b.status_code == 201, b.text


@pytest.mark.asyncio
async def test_une_source_supprimee_peut_etre_rajoutee(client, db_session, test_user):
    #: Sans cette exception, se tromper puis supprimer rendrait la reference
    #: definitivement inajoutable, et rien ne dirait pourquoi.
    card_id = await _cree_fiche(db_session, test_user, "source-supprimee")

    premier = await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())
    assert premier.status_code == 201

    suppression = await client.delete(f"/api/v1/sources/{premier.json()['id']}")
    assert suppression.status_code in (200, 204), suppression.text

    second = await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())

    assert second.status_code == 201, second.text


@pytest.mark.asyncio
async def test_un_lot_ecarte_les_doublons_sans_echouer(client, db_session, test_user):
    #: Le lot est le chemin de l'import. Un doublon n'y est pas une erreur a
    #: montrer a l'utilisateur : c'est une reference deja connue, qu'on compte
    #: a part pour que le total annonce reste honnete.
    card_id = await _cree_fiche(db_session, test_user, "lot-avec-doublons")

    await client.post(f"/api/v1/sources?card_id={card_id}", json=_source())

    lot = await client.post(
        f"/api/v1/sources/batch?card_id={card_id}",
        json={
            "sources": [
                _source(),
                _source(url="https://doi.org/10.1038/s41467-025-64094-7", title="Real-world data"),
                _source(url="https://doi.org/10.1038/s41467-025-64094-7", title="Le meme, encore"),
            ]
        },
    )

    assert lot.status_code == 201, lot.text
    corps = lot.json()
    assert len(corps["created"]) == 1
    assert corps["failed"] == []
    #: Un doublon deja en base, un doublon interne au lot.
    assert len(corps["duplicates"]) == 2
