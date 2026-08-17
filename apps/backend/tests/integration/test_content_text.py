"""Le texte integral du contenu documente : upload, PATCH, exposition publique.

Un createur qui a le droit de publier son texte (article propre, contenu libre
de droit, extrait sous droit de citation) doit pouvoir soit le coller
directement (PATCH content_text), soit deposer un fichier (upload). Le backend
fait confiance sur le droit ; l'UI porte le warning en amont.
"""

from __future__ import annotations

import io
import zipfile
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


@pytest_asyncio.fixture
async def owned_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="ma-fiche-avec-texte",
        title="Ma fiche avec texte",
        content_type="article",
        platform="other",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


def _docx_bytes(text: str) -> bytes:
    """Minimal DOCX qu'extract_text peut lire (word/document.xml suffit)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"/>',
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.'
            'org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            f"{text}"
            "</w:t></w:r></w:p></w:body></w:document>",
        )
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_pdf_texte_extrait_dans_content_text(client, session_token, owned_card):
    """Un DOCX minimal upload -> son texte se retrouve dans content_text."""
    client.cookies.set("filum_session", session_token)
    file_data = _docx_bytes("Le contenu integral du texte.")
    r = await client.post(
        f"/api/v1/cards/{owned_card.id}/content-text/upload",
        files={"file": ("mon-texte.docx", file_data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Le contenu integral du texte" in body["content_text"]


@pytest.mark.asyncio
async def test_upload_par_autrui_est_refuse(client, session_token, db_session):
    """La fiche d'un autre user est protegee."""
    from app.models.biblio_card import BiblioCard
    from app.models.user import User

    autre = User(
        id=uuid4(),
        email="autre@example.org",
        username="autre-user",
        display_name="Autre",
        public_key="a" * 64,
        encrypted_private_key="k",
        google_id="g_autre_ct",
        is_verified=True,
    )
    db_session.add(autre)
    await db_session.flush()
    card = BiblioCard(
        id=uuid4(),
        user_id=autre.id,
        slug="fiche-d-autrui",
        title="D'autrui",
        content_type="article",
        platform="other",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()

    client.cookies.set("filum_session", session_token)
    r = await client.post(
        f"/api/v1/cards/{card.id}/content-text/upload",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_upload_fichier_binaire_inconnu_est_refuse_avec_message(
    client, session_token, owned_card
):
    """Un .exe ou .png doit tomber en 422 avec un message qui dit quoi faire."""
    client.cookies.set("filum_session", session_token)
    r = await client.post(
        f"/api/v1/cards/{owned_card.id}/content-text/upload",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"x" * 200, "image/png")},
    )
    assert r.status_code == 422
    body = r.json()
    detail = body.get("detail") or body.get("error") or {}
    assert detail.get("code") == "unreadable_document"


@pytest.mark.asyncio
async def test_patch_content_text_avec_texte_colle(client, session_token, owned_card):
    """L'autre voie : coller directement le texte, sans fichier."""
    client.cookies.set("filum_session", session_token)
    r = await client.patch(
        f"/api/v1/cards/{owned_card.id}",
        json={"content_text": "Texte colle par l'utilisateur.\n\nDeuxieme paragraphe."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["content_text"] == "Texte colle par l'utilisateur.\n\nDeuxieme paragraphe."


@pytest.mark.asyncio
async def test_patch_content_text_chaine_vide_efface_le_texte(
    client, session_token, owned_card, db_session
):
    """L'user a coche « retirer le texte » : PATCH avec chaine vide efface."""
    owned_card.content_text = "Un texte existant."
    await db_session.commit()

    client.cookies.set("filum_session", session_token)
    r = await client.patch(
        f"/api/v1/cards/{owned_card.id}",
        json={"content_text": ""},
    )
    assert r.status_code == 200
    assert r.json()["content_text"] is None


@pytest.mark.asyncio
async def test_content_text_expose_sur_la_fiche_publique(
    client, session_token, owned_card, db_session, test_user
):
    """Une fois posee et publiee, la fiche publique porte content_text."""
    from datetime import UTC, datetime

    owned_card.content_text = "Texte publie."
    owned_card.status = "published"
    owned_card.published_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()

    r = await client.get(f"/api/v1/@{test_user.username}/{owned_card.slug}")
    assert r.status_code == 200
    assert r.json()["content_text"] == "Texte publie."


@pytest.mark.asyncio
async def test_creer_une_fiche_avec_texte_deja_colle(client, session_token, test_user):
    """POST /cards peut porter content_text directement, pas seulement PATCH."""
    client.cookies.set("filum_session", session_token)
    r = await client.post(
        "/api/v1/cards",
        json={
            "slug": "fiche-avec-texte-a-la-creation",
            "title": "Fiche avec texte a la creation",
            "content_text": "Le texte integral pose des la creation.",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["content_text"] == "Le texte integral pose des la creation."
