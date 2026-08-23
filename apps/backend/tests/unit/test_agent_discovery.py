"""Tests du mode decouverte : quota, consommation, resolution du provider."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.agent_discovery import (
    ErreurQuota,
    consommer_message,
    discovery_est_actif,
    nom_public_provider,
    resoudre_provider_decouverte,
    verifier_quota,
)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "session_secret": "test-secret-for-ci-session-32chars",
        "master_encryption_key": "test-key-for-ci-encryption-32b!",
        "google_client_id": "test.apps.googleusercontent.com",
        "google_client_secret": "test-secret",
        "google_redirect_uri": "http://test/callback",
        "agent_discovery_enabled": True,
        "agent_discovery_api_key": "sk-test-discovery-key",
        "agent_discovery_provider": "deepseek",
        "agent_discovery_model": "deepseek-chat",
        "agent_discovery_daily_quota_messages": 5,
    }
    base.update(overrides)
    return Settings(**base)


# ---------------------------------------------------------------------------
# discovery_est_actif
# ---------------------------------------------------------------------------


def test_discovery_actif_si_enabled_et_cle():
    s = _settings()
    assert discovery_est_actif(s) is True


def test_discovery_inactif_si_disabled():
    s = _settings(agent_discovery_enabled=False)
    assert discovery_est_actif(s) is False


def test_discovery_inactif_si_cle_vide():
    s = _settings(agent_discovery_api_key="")
    assert discovery_est_actif(s) is False


# ---------------------------------------------------------------------------
# nom_public_provider
# ---------------------------------------------------------------------------


def test_nom_public_deepseek():
    s = _settings(agent_discovery_provider="deepseek")
    assert nom_public_provider(s) == "DeepSeek"


def test_nom_public_groq():
    s = _settings(agent_discovery_provider="groq")
    assert nom_public_provider(s) == "Groq"


def test_nom_public_inconnu_retourne_kind():
    s = _settings(agent_discovery_provider="monprovider")
    assert nom_public_provider(s) == "monprovider"


# ---------------------------------------------------------------------------
# resoudre_provider_decouverte
# ---------------------------------------------------------------------------


def test_provider_decouverte_est_transient():
    s = _settings()
    p = resoudre_provider_decouverte(s)
    # Pas un vrai UUID de base : creator_id est l'UUID zero
    assert p.creator_id == uuid.UUID(int=0)
    assert p.model == "deepseek-chat"
    assert p.provider == "deepseek"
    assert p.is_default is True
    # La cle est chiffree, pas en clair
    assert p.api_key_enc != "sk-test-discovery-key"


# ---------------------------------------------------------------------------
# verifier_quota + consommer_message
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_vide(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest.mark.asyncio
async def test_quota_disponible_sans_ligne(db_session: AsyncSession):
    creator_id = uuid.uuid4()
    s = _settings(agent_discovery_daily_quota_messages=5)
    remaining = await verifier_quota(db_session, creator_id, s)
    assert remaining == 5


@pytest.mark.asyncio
async def test_quota_diminue_apres_consommation(db_session: AsyncSession):
    creator_id = uuid.uuid4()
    s = _settings(agent_discovery_daily_quota_messages=5)
    await consommer_message(db_session, creator_id, s)
    remaining = await verifier_quota(db_session, creator_id, s)
    assert remaining == 4


@pytest.mark.asyncio
async def test_quota_bloque_apres_N_messages(db_session: AsyncSession):
    creator_id = uuid.uuid4()
    s = _settings(agent_discovery_daily_quota_messages=3)
    for _ in range(3):
        await consommer_message(db_session, creator_id, s)
    with pytest.raises(ErreurQuota) as exc_info:
        await verifier_quota(db_session, creator_id, s)
    assert exc_info.value.quota == 3
    assert exc_info.value.remaining == 0


@pytest.mark.asyncio
async def test_quota_isole_par_creator(db_session: AsyncSession):
    creator_a = uuid.uuid4()
    creator_b = uuid.uuid4()
    s = _settings(agent_discovery_daily_quota_messages=2)
    await consommer_message(db_session, creator_a, s)
    await consommer_message(db_session, creator_a, s)
    # creator_b n'a pas encore consomme
    remaining_b = await verifier_quota(db_session, creator_b, s)
    assert remaining_b == 2
    # creator_a est a zero
    with pytest.raises(ErreurQuota):
        await verifier_quota(db_session, creator_a, s)


@pytest.mark.asyncio
async def test_consommer_idempotent_par_appels_successifs(db_session: AsyncSession):
    creator_id = uuid.uuid4()
    s = _settings(agent_discovery_daily_quota_messages=10)
    for _ in range(7):
        await consommer_message(db_session, creator_id, s)
    remaining = await verifier_quota(db_session, creator_id, s)
    assert remaining == 3
