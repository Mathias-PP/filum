"""Endpoints d'attestation — contrat HTTP autour d'ADR-019.

Trois routes : POST /attestations/content (auth requise), GET
/attestations/{id} (public), GET /attestations/{id}/verify (public). C'est la
promesse produit exposee au web : ces routes doivent refuser l'anonyme quand
attendu, retourner le corps signe intact, et rendre un verdict qui distingue
signature valide, hash falsifie et signature bricolee.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.crypto.keygen import KeyManager
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
async def attesting_user(db_session):
    """User avec vraie paire de cles Ed25519 : requis pour signer."""
    from app.core.config import get_settings
    from app.models.user import User

    settings = get_settings()
    km = KeyManager(settings.master_encryption_key)
    private_pem, _, public_hex = KeyManager.generate_keypair()

    user = User(
        id=uuid4(),
        email="attest@example.com",
        username="attest-user",
        display_name="Attest User",
        public_key=public_hex,
        encrypted_private_key=km.encrypt_private_key(private_pem),
        google_id="google_attest_int",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def attesting_token(auth_service, attesting_user) -> str:
    return auth_service.create_session(attesting_user.id)


@pytest.mark.asyncio
async def test_creer_attestation_sans_auth_est_refuse(client):
    """La signature engage un compte : personne d'anonyme ne peut la produire."""
    r = await client.post("/api/v1/attestations/content", json={"content_url": "https://ex.org/x"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_creer_attestation_avec_auth_retourne_201_et_signature(
    client, attesting_token, attesting_user
):
    client.cookies.set("filum_session", attesting_token)
    r = await client.post(
        "/api/v1/attestations/content",
        json={"content_url": "https://ex.org/mon-contenu"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"]
    assert body["user_id"] == str(attesting_user.id)
    assert body["content_url"] == "https://ex.org/mon-contenu"
    assert body["attested_at"]
    assert body["canonical_hash"] and len(body["canonical_hash"]) == 64
    assert body["signature"]
    assert body["created_at"]


@pytest.mark.asyncio
async def test_get_attestation_est_public(client, attesting_token, attesting_user):
    """Une attestation est un fait public : personne n'a besoin de s'authentifier
    pour lire ce qui a ete signe."""
    client.cookies.set("filum_session", attesting_token)
    created = (
        await client.post(
            "/api/v1/attestations/content", json={"content_url": "https://ex.org/lisible"}
        )
    ).json()
    # Recharge sans cookie.
    client.cookies.clear()
    r = await client.get(f"/api/v1/attestations/{created['id']}")
    assert r.status_code == 200
    assert r.json()["signature"] == created["signature"]


@pytest.mark.asyncio
async def test_get_attestation_inconnue_rend_404(client):
    r = await client.get(f"/api/v1/attestations/{uuid4()}")
    assert r.status_code == 404
    body = r.json()
    # Le handler d'erreur global peut normaliser en {"error": ...} ou laisser
    # le {"detail": ...} de FastAPI. Les deux doivent porter le code.
    code = (body.get("detail") or body.get("error") or {}).get("code")
    assert code == "not_found"


@pytest.mark.asyncio
async def test_verify_attestation_valide_rend_valid_true(client, attesting_token, attesting_user):
    """Le happy path : signature fraiche, cle publique inchangee -> valid."""
    client.cookies.set("filum_session", attesting_token)
    created = (
        await client.post(
            "/api/v1/attestations/content", json={"content_url": "https://ex.org/verifiable"}
        )
    ).json()
    client.cookies.clear()
    r = await client.get(f"/api/v1/attestations/{created['id']}/verify")
    assert r.status_code == 200
    verdict = r.json()
    assert verdict["valid"] is True
    assert verdict["creator_slug"] == attesting_user.username
    assert verdict["public_key"] == attesting_user.public_key
    assert verdict["content_url"] == "https://ex.org/verifiable"


@pytest.mark.asyncio
async def test_verify_attestation_inconnue_rend_404(client):
    r = await client.get(f"/api/v1/attestations/{uuid4()}/verify")
    assert r.status_code == 404
