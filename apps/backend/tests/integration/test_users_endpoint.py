"""Endpoint /users/@slug — page-identite publique du createur.

C'est ce que voit un lecteur qui clique sur `/@lea-c` : profil, comptes lies,
liste des fiches publiees. Contrat testable a plusieurs niveaux :

- 404 sur slug inconnu, pas 500 ni 401.
- Un brouillon ou une fiche privee ne fuit jamais dans la liste publique.
- `total_sources` compte les sources non supprimees.
- Les comptes lies non verifies apparaissent (marques verified=false), c'est
  au lecteur de decider ce qu'il en fait.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_profil_inconnu_rend_404(client):
    r = await client.get("/api/v1/users/@fantome")
    assert r.status_code == 404
    body = r.json()
    code = (body.get("detail") or body.get("error") or {}).get("code")
    assert code == "not_found"


@pytest.mark.asyncio
async def test_profil_existant_rend_les_champs_publics(client, test_user):
    r = await client.get(f"/api/v1/users/@{test_user.username}")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == test_user.username
    assert body["display_name"] == test_user.display_name
    assert body["public_key"] == test_user.public_key
    assert body["stats"]["total_cards"] == 0
    assert body["stats"]["total_sources"] == 0
    assert body["cards"] == []
    assert body["linked_accounts"] == []


@pytest.mark.asyncio
async def test_les_fiches_brouillon_n_apparaissent_pas(client, db_session, test_user):
    from app.models.biblio_card import BiblioCard

    db_session.add(
        BiblioCard(
            id=uuid4(),
            user_id=test_user.id,
            slug="brouillon",
            title="Brouillon",
            content_type="video",
            platform="youtube",
            status="draft",
            visibility="public",
        )
    )
    await db_session.commit()
    r = await client.get(f"/api/v1/users/@{test_user.username}")
    assert r.status_code == 200
    assert r.json()["stats"]["total_cards"] == 0
    assert r.json()["cards"] == []


@pytest.mark.asyncio
async def test_les_fiches_privees_n_apparaissent_pas(client, db_session, test_user):
    """Une fiche `published + visibility=private` reste sur le dashboard, pas
    sur la page publique. Sinon toute fiche « publiee mais reservee » fuiterait
    ici avec son slug et son titre."""
    from datetime import UTC, datetime

    from app.models.biblio_card import BiblioCard

    db_session.add(
        BiblioCard(
            id=uuid4(),
            user_id=test_user.id,
            slug="secrete",
            title="Fiche secrete",
            content_type="video",
            platform="youtube",
            status="published",
            visibility="private",
            published_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db_session.commit()
    r = await client.get(f"/api/v1/users/@{test_user.username}")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["total_cards"] == 0
    assert not any(c["slug"] == "secrete" for c in body["cards"])


@pytest.mark.asyncio
async def test_les_fiches_publiques_apparaissent_avec_leur_total_sources(
    client, db_session, test_user
):
    from datetime import UTC, datetime
    from uuid import uuid4 as _u

    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    now = datetime.now(UTC).replace(tzinfo=None)
    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="visible",
        title="Fiche visible",
        content_type="video",
        platform="youtube",
        status="published",
        visibility="public",
        published_at=now,
    )
    db_session.add(card)
    await db_session.flush()
    for i in range(3):
        db_session.add(
            Source(
                id=_u(),
                biblio_card_id=card.id,
                position=i,
                url=f"https://ex.org/{i}",
                format="texte",
                category="article-scientifique",
                author_kind="chercheur",
            )
        )
    # Une 4e supprimee : ne doit pas compter.
    db_session.add(
        Source(
            id=_u(),
            biblio_card_id=card.id,
            position=99,
            url="https://ex.org/deleted",
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
            deleted_at=now,
        )
    )
    await db_session.commit()
    r = await client.get(f"/api/v1/users/@{test_user.username}")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["total_cards"] == 1
    assert body["stats"]["total_sources"] == 3
    assert body["cards"][0]["slug"] == "visible"
    assert body["cards"][0]["total_sources"] == 3


@pytest.mark.asyncio
async def test_first_et_last_published_at_bornent_l_activite(client, db_session, test_user):
    from datetime import UTC, datetime, timedelta

    from app.models.biblio_card import BiblioCard

    base = datetime.now(UTC).replace(tzinfo=None)
    for i, slug in enumerate(["ancienne", "milieu", "recente"]):
        db_session.add(
            BiblioCard(
                id=uuid4(),
                user_id=test_user.id,
                slug=slug,
                title=slug.title(),
                content_type="video",
                platform="youtube",
                status="published",
                visibility="public",
                published_at=base - timedelta(days=10 - i * 3),
            )
        )
    await db_session.commit()
    body = (await client.get(f"/api/v1/users/@{test_user.username}")).json()
    stats = body["stats"]
    assert stats["total_cards"] == 3
    # first = plus ancienne, last = plus recente. L'ordre du tableau `cards`
    # est descendant sur published_at.
    assert body["cards"][0]["slug"] == "recente"
    assert body["cards"][-1]["slug"] == "ancienne"
    assert stats["first_published_at"] < stats["last_published_at"]
