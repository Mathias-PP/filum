"""Archivage a la demande : POST /api/v1/sources/archive.

L'archivage automatique est cadence et peut prendre des heures sur une grosse
fiche. Cette route laisse designer ce qui presse. Elle doit surtout ne jamais
confondre les sorts possibles : « deja archivee », « rien a archiver » et
« deja en cours » ne sont pas « mise en file ».
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


@pytest_asyncio.fixture
async def card(db_session, test_user):
    from app.models.biblio_card import BiblioCard

    c = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-archivage",
        title="Fiche archivage",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(c)
    await db_session.commit()
    return c


async def _add_source(db_session, card, *, url: str, status: str, position: int):
    from app.models.source import Source

    s = Source(
        biblio_card_id=card.id,
        position=position,
        url=url,
        title=f"Source {position}",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
        archive_status=status,
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest.fixture
def captured(monkeypatch):
    """Intercepte la mise en file : le test ne doit appeler personne dehors."""
    calls: list[list] = []

    def fake(pairs):
        calls.append(list(pairs))
        return len(pairs)

    monkeypatch.setattr("app.api.v1.endpoints.sources.schedule_archiving", fake)
    return calls


@pytest.mark.asyncio
async def test_met_en_file_une_source_pendante(client, db_session, card, captured):
    s = await _add_source(
        db_session, card, url="https://example.org/a", status="pending", position=1
    )

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(s.id)]})

    assert resp.status_code == 200
    assert resp.json() == {
        "scheduled": 1,
        "already_archived": 0,
        "nothing_to_archive": 0,
        "already_running": 0,
    }
    assert captured == [[(s.id, "https://example.org/a")]]


@pytest.mark.asyncio
async def test_met_en_file_un_lot(client, db_session, card, captured):
    a = await _add_source(
        db_session, card, url="https://example.org/a", status="pending", position=1
    )
    b = await _add_source(
        db_session, card, url="https://example.org/b", status="failed", position=2
    )

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(a.id), str(b.id)]})

    assert resp.json()["scheduled"] == 2
    assert {sid for sid, _ in captured[0]} == {a.id, b.id}


@pytest.mark.asyncio
async def test_une_source_deja_archivee_n_est_pas_relancee(client, db_session, card, captured):
    # Redemander une capture deja obtenue depenserait le quota Save Page Now
    # pour rien.
    s = await _add_source(
        db_session, card, url="https://example.org/a", status="archived", position=1
    )

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(s.id)]})

    body = resp.json()
    assert body["already_archived"] == 1
    assert body["scheduled"] == 0
    assert captured == []


@pytest.mark.asyncio
async def test_sans_url_n_est_pas_un_echec_d_archivage(client, db_session, card, captured):
    # Un chapitre de livre n'a rien a archiver : le compter comme un echec
    # ferait croire que la page est perdue.
    s = await _add_source(db_session, card, url="", status="not_applicable", position=1)

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(s.id)]})

    body = resp.json()
    assert body["nothing_to_archive"] == 1
    assert body["scheduled"] == 0
    assert captured == []


@pytest.mark.asyncio
async def test_deja_en_cours_n_est_pas_compte_comme_mis_en_file(
    client, db_session, card, monkeypatch
):
    s = await _add_source(
        db_session, card, url="https://example.org/a", status="pending", position=1
    )
    monkeypatch.setattr("app.api.v1.endpoints.sources.schedule_archiving", lambda pairs: 0)

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(s.id)]})

    body = resp.json()
    assert body["already_running"] == 1
    assert body["scheduled"] == 0


@pytest.mark.asyncio
async def test_source_d_autrui_est_indistinguable_d_une_source_absente(
    client, db_session, test_user, captured
):
    # Repondre 403 dirait qu'elle existe.
    from app.models.biblio_card import BiblioCard
    from app.models.user import User

    other = User(
        id=uuid4(),
        email="autre@example.org",
        username=f"autre-{uuid4().hex[:8]}",
        public_key="t" * 64,
        encrypted_private_key="t" * 64,
        google_id=f"g-{uuid4()}",
    )
    db_session.add(other)
    await db_session.flush()
    foreign = BiblioCard(
        id=uuid4(),
        user_id=other.id,
        slug="fiche-autrui",
        title="Fiche d'autrui",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(foreign)
    await db_session.commit()
    s = await _add_source(
        db_session, foreign, url="https://example.org/x", status="pending", position=1
    )

    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(s.id)]})

    assert resp.status_code == 404
    assert captured == []


@pytest.mark.asyncio
async def test_source_inconnue_repond_404(client, captured):
    resp = await client.post("/api/v1/sources/archive", json={"source_ids": [str(uuid4())]})
    assert resp.status_code == 404
    assert captured == []


@pytest.mark.asyncio
async def test_liste_vide_ne_declenche_rien(client, captured):
    resp = await client.post("/api/v1/sources/archive", json={"source_ids": []})
    assert resp.status_code == 200
    assert resp.json()["scheduled"] == 0
    assert captured == []
