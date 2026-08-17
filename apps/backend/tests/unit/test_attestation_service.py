"""AttestationService — le coeur cryptographique du produit (ADR-019).

La signature Ed25519 sur le triplet `(user_id, content_url, attested_at)` est
la promesse produit : une fiche peut muter, l'attestation reste. Toute
modification silencieuse du canonical hash ou de la logique de verification
casserait toutes les attestations existantes -- et personne ne verrait
l'incident avant qu'un lecteur tente de verifier.

Ces tests couvrent : creation, get, verify (valide / hash mismatch / signature
mismatch), et le round-trip complet.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.crypto.keygen import KeyManager
from app.services.attestation import AttestationService


@pytest_asyncio.fixture
async def attesting_user(db_session):
    """Utilisateur avec une vraie paire de cles Ed25519 chiffree AES-GCM.

    La fixture `test_user` porte des chaines factices ("t"*64) qui suffisent
    aux tests d'auth mais pas a une signature reelle : `decrypt_private_key`
    echoue en base64.
    """
    from app.core.config import get_settings
    from app.models.user import User

    settings = get_settings()
    km = KeyManager(settings.master_encryption_key)
    private_pem, _public_pem, public_hex = KeyManager.generate_keypair()
    encrypted = km.encrypt_private_key(private_pem)

    user = User(
        id=uuid4(),
        email="attest@example.com",
        username="attestuser",
        display_name="Attest User",
        public_key=public_hex,
        encrypted_private_key=encrypted,
        google_id="google_attest",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def service(db_session):
    return AttestationService(db_session)


@pytest.mark.asyncio
async def test_creer_une_attestation_produit_une_signature_verifiable(
    db_session, service, attesting_user
):
    attestation = await service.create_attestation(attesting_user, "https://ex.org/video/1")
    assert attestation.id is not None
    assert attestation.user_id == attesting_user.id
    assert attestation.content_url == "https://ex.org/video/1"
    assert attestation.attested_at is not None
    assert attestation.canonical_hash
    assert len(attestation.canonical_hash) == 64  # sha256 hex
    assert attestation.signature
    # Round-trip immediat : la signature qu'on vient de produire doit valider
    # contre la cle publique du meme user.
    verdict = await service.verify_attestation(attestation)
    assert verdict["valid"] is True
    assert verdict["creator_slug"] == "attestuser"
    assert verdict["public_key"] == attesting_user.public_key


@pytest.mark.asyncio
async def test_get_attestation_charge_l_utilisateur(db_session, service, attesting_user):
    """La verification a besoin de la cle publique, donc `user` doit etre eager-load."""
    attestation = await service.create_attestation(attesting_user, "https://ex.org/2")
    retrouvee = await service.get_attestation(attestation.id)
    assert retrouvee is not None
    assert retrouvee.user.public_key == attesting_user.public_key


@pytest.mark.asyncio
async def test_get_attestation_inconnue_rend_none(service):
    assert await service.get_attestation(uuid4()) is None


@pytest.mark.asyncio
async def test_verify_detecte_un_hash_falsifie(db_session, service, attesting_user):
    """Un lecteur qui modifie l'URL apres coup ne peut pas se cacher."""
    attestation = await service.create_attestation(attesting_user, "https://ex.org/original")
    # Modification malveillante du contenu attest : le hash ne colle plus.
    attestation.content_url = "https://ex.org/redirect-vers-arnaque"
    # Rechargeons pour que verify_attestation ait bien l'user attache.
    rechargee = await service.get_attestation(attestation.id)
    # Simulons la falsification en memoire (sans commit).
    rechargee.content_url = "https://ex.org/redirect-vers-arnaque"
    verdict = await service.verify_attestation(rechargee)
    assert verdict["valid"] is False
    assert verdict["reason"] == "hash_mismatch"
    assert verdict["expected_hash"] != verdict["computed_hash"]


@pytest.mark.asyncio
async def test_verify_detecte_une_signature_falsifiee(db_session, service, attesting_user):
    """Une signature bricolee doit tomber au verify, meme si le hash colle."""
    attestation = await service.create_attestation(attesting_user, "https://ex.org/vrai")
    rechargee = await service.get_attestation(attestation.id)
    # Bricoler la signature en gardant le hash intact : le path "signature_mismatch".
    rechargee.signature = "00" * 64
    verdict = await service.verify_attestation(rechargee)
    assert verdict["valid"] is False
    assert verdict["reason"] == "signature_mismatch"


@pytest.mark.asyncio
async def test_verify_detecte_une_cle_publique_qui_ne_correspond_pas(
    db_session, service, attesting_user
):
    """Un imposteur qui remplace le public_key ne peut plus verifier."""
    attestation = await service.create_attestation(attesting_user, "https://ex.org/3")
    # Autre user avec autre cle publique : le mapping user->cle est le lien
    # que la signature protege.
    _, _, other_public_hex = KeyManager.generate_keypair()
    attesting_user.public_key = other_public_hex
    await db_session.commit()
    rechargee = await service.get_attestation(attestation.id)
    verdict = await service.verify_attestation(rechargee)
    assert verdict["valid"] is False
    assert verdict["reason"] == "signature_mismatch"


@pytest.mark.asyncio
async def test_deux_attestations_du_meme_contenu_ont_des_horodatages_distincts(
    db_session, service, attesting_user
):
    """Chaque attestation est unique par son `attested_at`. Deux appels
    successifs pour la meme URL produisent deux attestations differentes
    (sans quoi le triplet signe serait ambigu)."""
    import asyncio

    a1 = await service.create_attestation(attesting_user, "https://ex.org/dup")
    await asyncio.sleep(0.001)  # granularite datetime
    a2 = await service.create_attestation(attesting_user, "https://ex.org/dup")
    assert a1.id != a2.id
    assert a1.attested_at != a2.attested_at
    assert a1.canonical_hash != a2.canonical_hash
    assert a1.signature != a2.signature
