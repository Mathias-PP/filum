"""Tests du mode gratuit : consentement versionne, routeur de lanes, quotas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_lane import AgentGratuitConsent, AgentLane, AgentLaneUsage
from app.services import agent_gratuit


@pytest.fixture
def settings_actives(monkeypatch):
    """Instance active + cle Z.ai presente, sans toucher l'environment."""
    s = get_settings()
    monkeypatch.setattr(s, "agent_gratuit_enabled", True)
    monkeypatch.setattr(s, "agent_gratuit_zai_api_key", "zai-key-test")
    return s


@pytest.fixture
async def lane_zai(db_session):
    lane = AgentLane(
        id=uuid4(),
        slug="zai",
        label_public="GLM · Z.ai",
        provider_kind="custom",
        base_url="https://api.z.ai/api/paas/v4",
        model="glm-5.2",
        rpm_cap=3,
        rpd_cap=900,
        actif=True,
        position=0,
    )
    db_session.add(lane)
    await db_session.commit()
    await db_session.refresh(lane)
    return lane


# ---------------------------------------------------------------------------
# Disponibilite
# ---------------------------------------------------------------------------


def test_mode_indisponible_par_defaut():
    assert agent_gratuit.mode_disponible() is False


def test_disponible_si_active_avec_cle(settings_actives):
    assert agent_gratuit.mode_disponible() is True


def test_inactive_sans_cle(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "agent_gratuit_enabled", True)
    monkeypatch.setattr(s, "agent_gratuit_zai_api_key", "")
    assert agent_gratuit.mode_disponible() is False


# ---------------------------------------------------------------------------
# Consentement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConsentement:
    async def test_inactif_avant_consentement(self, db_session, test_user, settings_actives):
        etat = await agent_gratuit.etat_consentement(db_session, test_user.id)
        assert etat == {
            "disponible": True,
            "actif": False,
            "version_warning": agent_gratuit.VERSION_WARNING,
        }

    async def test_donner_puis_retirer(self, db_session, test_user, settings_actives):
        await agent_gratuit.donner_consentement(
            db_session, test_user.id, agent_gratuit.VERSION_WARNING
        )
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is True
        await agent_gratuit.retirer_consentement(db_session, test_user.id)
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is False

    async def test_version_inconnue_refusee(self, db_session, test_user, settings_actives):
        with pytest.raises(ValueError, match="version_warning_inconnue"):
            await agent_gratuit.donner_consentement(db_session, test_user.id, "1999-01-01-v0")

    async def test_reconsentir_ecrase_la_version(self, db_session, test_user):
        db_session.add(
            AgentGratuitConsent(
                creator_id=str(test_user.id),
                version="ancienne-v1",
                consent_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()
        # Un utilisateur ayant consenti a une vieille version n'est pas couvert.
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is False
        await agent_gratuit.donner_consentement(
            db_session, test_user.id, agent_gratuit.VERSION_WARNING
        )
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is True


# ---------------------------------------------------------------------------
# Routeur de lanes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestChoisirLane:
    async def test_rend_un_provider_transient_operationnel(
        self, db_session, test_user, lane_zai, settings_actives
    ):
        choisi = await agent_gratuit.choisir_lane(db_session)
        assert choisi is not None
        assert choisi.lane.slug == "zai"
        p = choisi.provider
        assert p.provider == "custom"
        assert p.base_url == "https://api.z.ai/api/paas/v4"
        assert p.model == "glm-5.2"
        cle = KeyManager(get_settings().master_encryption_key).decrypt_private_key(p.api_key_enc)
        assert cle == "zai-key-test"

    async def test_ignore_une_lane_sans_cle(self, db_session, lane_zai):
        # Instance active mais pas de cle configuree pour cette lane.
        assert await agent_gratuit.choisir_lane(db_session) is None

    async def test_ignore_une_lane_desactivee(self, db_session, lane_zai, settings_actives):
        lane_zai.actif = False
        await db_session.commit()
        assert await agent_gratuit.choisir_lane(db_session) is None

    async def test_saute_la_lane_en_cooldown(self, db_session, lane_zai, settings_actives):
        await agent_gratuit.signaler_echec(db_session, lane_zai, minutes=10)
        assert await agent_gratuit.choisir_lane(db_session) is None

    async def test_le_cooldown_expire(self, db_session, lane_zai, settings_actives):
        from datetime import date

        passe = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        db_session.add(
            AgentLaneUsage(
                id=uuid4(), lane_id=lane_zai.id, date=date.today(), cooldown_until=passe
            )
        )
        await db_session.commit()
        choisi = await agent_gratuit.choisir_lane(db_session)
        assert choisi is not None and choisi.lane.id == lane_zai.id

    async def test_saute_la_lane_saturee(self, db_session, lane_zai, settings_actives):
        from datetime import date

        db_session.add(
            AgentLaneUsage(id=uuid4(), lane_id=lane_zai.id, date=date.today(), requests_used=900)
        )
        await db_session.commit()
        assert await agent_gratuit.choisir_lane(db_session) is None

    async def test_ordre_de_position_respecte(
        self, db_session, lane_zai, settings_actives
    ):
        seconde = AgentLane(
            id=uuid4(),
            slug="autre",
            label_public="Autre",
            provider_kind="custom",
            base_url="https://exemple.org/v1",
            model="m1",
            actif=True,
            position=5,
        )
        db_session.add(seconde)
        await db_session.commit()
        # Pas de cle « autre » dans les settings : seule zai est eligible.
        choisi = await agent_gratuit.choisir_lane(db_session)
        assert choisi is not None and choisi.lane.slug == "zai"


# ---------------------------------------------------------------------------
# Consommation et quota utilisateur
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQuotas:
    async def test_consommer_requete_increment(self, db_session, lane_zai):
        await agent_gratuit.consommer_requete(db_session, lane_zai)
        await agent_gratuit.consommer_requete(db_session, lane_zai)
        from sqlalchemy import select
        from datetime import date

        row = (
            await db_session.execute(
                select(AgentLaneUsage).where(AgentLaneUsage.lane_id == lane_zai.id)
            )
        ).scalar_one()
        assert row.requests_used == 2 and row.date == date.today()

    async def test_quota_utilisateur_bloque_a_epuisement(
        self, db_session, test_user, monkeypatch
    ):
        s = get_settings()
        monkeypatch.setattr(s, "agent_gratuit_daily_quota_messages", 2)
        await agent_gratuit.consommer_message_utilisateur(db_session, test_user.id)
        await agent_gratuit.consommer_message_utilisateur(db_session, test_user.id)
        with pytest.raises(agent_gratuit.ErreurQuotaGratuit):
            await agent_gratuit.verifier_quota_utilisateur(db_session, test_user.id)

    async def test_restant_decroit(self, db_session, test_user, monkeypatch):
        s = get_settings()
        monkeypatch.setattr(s, "agent_gratuit_daily_quota_messages", 5)
        assert await agent_gratuit.verifier_quota_utilisateur(db_session, test_user.id) == 5
        await agent_gratuit.consommer_message_utilisateur(db_session, test_user.id)
        assert await agent_gratuit.verifier_quota_utilisateur(db_session, test_user.id) == 4
