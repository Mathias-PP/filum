"""Tests du mode gratuit : consentement versionne, routeur de lanes, quotas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
        model="glm-4.7-flash",
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
            "fournisseur_actuel": None,
            "modele_actuel": None,
        }

    async def test_actif_expose_le_fournisseur_qui_sert_le_prochain_tour(
        self, db_session, test_user, settings_actives, lane_zai
    ):
        await agent_gratuit.donner_consentement(
            db_session, test_user.id, agent_gratuit.VERSION_WARNING
        )
        etat = await agent_gratuit.etat_consentement(db_session, test_user.id)
        assert etat["actif"] is True
        assert etat["fournisseur_actuel"] == lane_zai.label_public
        assert etat["modele_actuel"] == lane_zai.model

        # Lane desactivee : plus de fournisseur, le mode ne peut plus servir.
        lane_zai.actif = False
        etat = await agent_gratuit.etat_consentement(db_session, test_user.id)
        assert etat["actif"] is True
        assert etat["fournisseur_actuel"] is None
        assert etat["modele_actuel"] is None

    async def test_donner_puis_retirer(self, db_session, test_user, settings_actives):
        await agent_gratuit.donner_consentement(
            db_session, test_user.id, agent_gratuit.VERSION_WARNING
        )
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is True
        await agent_gratuit.retirer_consentement(db_session, test_user.id)
        assert await agent_gratuit.est_consentant(db_session, test_user.id) is False

    async def test_consentement_ecrit_une_date_sans_fuseau(
        self, db_session, test_user, settings_actives, monkeypatch
    ):
        """`consent_at` est un `TIMESTAMP WITHOUT TIME ZONE`.

        Postgres refuse d'y ecrire un datetime « aware » : le mode gratuit
        rendait un 500 et etait inactivable. SQLite, lui, accepte l'ecriture et
        efface le fuseau a la relecture, donc relire la ligne ne prouve rien.
        On observe l'objet au moment ou il part vers la base : c'est la seule
        position ou ce test distingue le code correct du code fautif.
        """
        vus: list[datetime] = []
        vrai_merge = db_session.merge

        async def merge_espion(objet, *args, **kwargs):
            vus.append(objet.consent_at)
            return await vrai_merge(objet, *args, **kwargs)

        monkeypatch.setattr(db_session, "merge", merge_espion)
        await agent_gratuit.donner_consentement(
            db_session, test_user.id, agent_gratuit.VERSION_WARNING
        )
        assert vus and vus[0].tzinfo is None

    async def test_version_inconnue_refusee(self, db_session, test_user, settings_actives):
        with pytest.raises(ValueError, match="version_warning_inconnue"):
            await agent_gratuit.donner_consentement(db_session, test_user.id, "1999-01-01-v0")

    async def test_reconsentir_ecrase_la_version(self, db_session, test_user):
        db_session.add(
            AgentGratuitConsent(
                creator_id=str(test_user.id),
                version="ancienne-v1",
                consent_at=datetime.now(UTC),
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
        assert p.model == "glm-4.7-flash"
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

        passe = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        db_session.add(
            AgentLaneUsage(id=uuid4(), lane_id=lane_zai.id, date=date.today(), cooldown_until=passe)
        )
        await db_session.commit()
        choisi = await agent_gratuit.choisir_lane(db_session)
        assert choisi is not None and choisi.lane.id == lane_zai.id

    async def test_bascule_sur_la_lane_de_secours_en_cooldown(
        self, db_session, lane_zai, settings_actives
    ):
        """Le primaire sature (429) : les tours partent sur le secours."""
        lane_alt = AgentLane(
            id=uuid4(),
            slug="zai-alt",
            label_public="GLM · Z.ai (secours)",
            provider_kind="custom",
            base_url="https://api.z.ai/api/paas/v4",
            model="glm-4.5-flash",
            rpm_cap=3,
            rpd_cap=900,
            actif=True,
            position=10,
        )
        db_session.add(lane_alt)
        await agent_gratuit.signaler_echec(db_session, lane_zai)
        choisi = await agent_gratuit.choisir_lane(db_session)
        assert choisi is not None
        assert choisi.lane.slug == "zai-alt"
        # La cle du secours se resolve comme celle du primaire (meme compte).
        from app.crypto.keygen import KeyManager

        cle = KeyManager(get_settings().master_encryption_key).decrypt_private_key(
            choisi.provider.api_key_enc
        )
        assert cle == "zai-key-test"

    async def test_les_lanes_eligibles_sortent_toutes_dans_l_ordre(
        self, db_session, lane_zai, settings_actives
    ):
        """La liste sert de replis au tour en cours, pas seulement sa tete.

        Le cooldown ne repare que le tour suivant : sans repli disponible
        pendant le tour, une saturation du primaire rendait une erreur au
        createur alors que le secours pouvait repondre.
        """
        db_session.add(
            AgentLane(
                id=uuid4(),
                slug="zai-alt",
                label_public="GLM · Z.ai (secours)",
                provider_kind="custom",
                base_url="https://api.z.ai/api/paas/v4",
                model="glm-4.5-flash",
                actif=True,
                position=10,
            )
        )
        await db_session.commit()
        lanes = await agent_gratuit.lanes_eligibles(db_session)
        assert [item.lane.slug for item in lanes] == ["zai", "zai-alt"]
        # Chaque repli porte sa propre identite : la boucle de chat met les
        # providers au repos par id, deux ids egaux les confondraient.
        assert lanes[0].provider.id != lanes[1].provider.id

    async def test_saute_la_lane_saturee(self, db_session, lane_zai, settings_actives):
        from datetime import date

        db_session.add(
            AgentLaneUsage(id=uuid4(), lane_id=lane_zai.id, date=date.today(), requests_used=900)
        )
        await db_session.commit()
        assert await agent_gratuit.choisir_lane(db_session) is None

    async def test_ordre_de_position_respecte(self, db_session, lane_zai, settings_actives):
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
        from datetime import date

        from sqlalchemy import select

        row = (
            await db_session.execute(
                select(AgentLaneUsage).where(AgentLaneUsage.lane_id == lane_zai.id)
            )
        ).scalar_one()
        assert row.requests_used == 2 and row.date == date.today()

    async def test_quota_utilisateur_bloque_a_epuisement(self, db_session, test_user, monkeypatch):
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


# ---------------------------------------------------------------------------
# Testeur de lane (diagnostic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTesterLane:
    async def test_sans_lane_disponible(self, db_session, lane_zai):
        # Instance « activee » mais aucune cle configuree : aucune lane.
        r = await agent_gratuit.tester_lane(db_session)
        assert r["ok"] is False
        assert r["modele"] is None
        assert r["latence_ms"] is None

    async def test_ok_renvoie_modele_et_latence(
        self, db_session, lane_zai, settings_actives, monkeypatch
    ):
        from app.services import agent as agent_module

        async def faux_appel(provider, messages, outils, transport, **kw):
            assert transport is None
            return ({"role": "assistant", "content": "ok"}, "stop", {})

        monkeypatch.setattr(agent_module, "_appel_provider", faux_appel)
        r = await agent_gratuit.tester_lane(db_session)
        assert r["ok"] is True
        assert r["detail"] == "reponse recue"
        assert r["modele"] == "glm-4.7-flash"
        assert isinstance(r["latence_ms"], int)

    async def test_echec_provider_renvoie_le_detail(
        self, db_session, lane_zai, settings_actives, monkeypatch
    ):
        from app.services import agent as agent_module

        async def faux_appel(provider, messages, outils, transport, **kw):
            return "Le fournisseur (custom) refuse : quota ou limite de débit atteinte."

        monkeypatch.setattr(agent_module, "_appel_provider", faux_appel)
        r = await agent_gratuit.tester_lane(db_session)
        assert r["ok"] is False
        assert "quota" in r["detail"]
        assert r["modele"] == "glm-4.7-flash"

    async def test_erreur_reseau_capturee(
        self, db_session, lane_zai, settings_actives, monkeypatch
    ):
        from app.services import agent as agent_module

        async def faux_appel(provider, messages, outils, transport, **kw):
            raise RuntimeError("connect timeout")

        monkeypatch.setattr(agent_module, "_appel_provider", faux_appel)
        r = await agent_gratuit.tester_lane(db_session)
        assert r["ok"] is False
        assert "timeout" in r["detail"]

    async def test_nincremente_pas_les_compteurs(
        self, db_session, lane_zai, settings_actives, monkeypatch
    ):
        from datetime import date

        from sqlalchemy import select

        from app.services import agent as agent_module

        async def faux_appel(provider, messages, outils, transport, **kw):
            return ({"role": "assistant", "content": "ok"}, "stop", {})

        monkeypatch.setattr(agent_module, "_appel_provider", faux_appel)
        await agent_gratuit.tester_lane(db_session)
        lignes = (await db_session.execute(select(AgentLaneUsage))).scalars().all()
        assert lignes == []


# ---------------------------------------------------------------------------
# Catalogue de modeles + choix manuel du primaire
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestModeles:
    async def test_cle_lane_resout_les_lanes_zai(self, settings_actives):
        assert agent_gratuit.cle_lane("zai", settings_actives) == "zai-key-test"
        assert agent_gratuit.cle_lane("zai-alt", settings_actives) == "zai-key-test"
        assert agent_gratuit.cle_lane("autre", settings_actives) == ""

    async def test_liste_modeles_annote_le_role(self, db_session, lane_zai, settings_actives):
        lane_alt = AgentLane(
            id=uuid4(),
            slug="zai-alt",
            label_public="GLM · Z.ai (secours)",
            provider_kind="custom",
            base_url="https://api.z.ai/api/paas/v4",
            model="glm-4.5-flash",
            actif=True,
            position=10,
        )
        db_session.add(lane_alt)
        await db_session.commit()
        modeles = await agent_gratuit.liste_modeles(db_session)
        par_id = {m["model"]: m for m in modeles}
        assert set(par_id) == {"glm-4.7-flash", "glm-4.5-flash"}
        assert par_id["glm-4.7-flash"]["role"] == "primaire"
        assert par_id["glm-4.5-flash"]["role"] == "secours"
        assert all(m["actif"] for m in par_id.values())

    async def test_definir_primaire_change_la_lane_zai(
        self, db_session, lane_zai, settings_actives
    ):
        r = await agent_gratuit.definir_modele_primaire(db_session, "glm-4.5-flash")
        assert r["model"] == "glm-4.5-flash" and r["slug"] == "zai"
        await db_session.refresh(lane_zai)
        assert lane_zai.model == "glm-4.5-flash"

    async def test_definir_primaire_refuse_hors_catalogue(self, db_session, lane_zai):
        with pytest.raises(ValueError):
            await agent_gratuit.definir_modele_primaire(db_session, "glm-5.2")
        # La lane n'a pas bouge.
        await db_session.refresh(lane_zai)
        assert lane_zai.model == "glm-4.7-flash"

    async def test_definir_primaire_sans_lane_leve(self, db_session):
        with pytest.raises(ValueError):
            await agent_gratuit.definir_modele_primaire(db_session, "glm-4.7-flash")

    async def test_le_secours_ne_reste_pas_sur_le_modele_du_primaire(
        self, db_session, lane_zai, settings_actives
    ):
        """Sans cet ecart, le repli reproduit exactement l'echec du primaire.

        Les deux lanes partagent l'endpoint et la cle : le modele est la seule
        chose qui les distingue. C'est l'etat mesure en production le
        2026-08-31, ou basculer le primaire sur `glm-4.5-flash` avait aligne le
        secours dessus sans que rien ne le signale.
        """
        lane_alt = AgentLane(
            id=uuid4(),
            slug="zai-alt",
            label_public="GLM · Z.ai (secours)",
            provider_kind="custom",
            base_url="https://api.z.ai/api/paas/v4",
            model="glm-4.5-flash",
            actif=True,
            position=10,
        )
        db_session.add(lane_alt)
        await db_session.commit()

        r = await agent_gratuit.definir_modele_primaire(db_session, "glm-4.5-flash")

        await db_session.refresh(lane_alt)
        assert lane_alt.model == "glm-4.7-flash"
        assert r["secours"] == [{"slug": "zai-alt", "model": "glm-4.7-flash"}]

    async def test_liste_modeles_ne_confond_pas_deux_lanes_de_meme_modele(
        self, db_session, lane_zai, settings_actives
    ):
        """Indexer les lanes par modele en perdait une, et faussait les roles."""
        lane_zai.model = "glm-4.5-flash"
        db_session.add(
            AgentLane(
                id=uuid4(),
                slug="zai-alt",
                label_public="GLM · Z.ai (secours)",
                provider_kind="custom",
                base_url="https://api.z.ai/api/paas/v4",
                model="glm-4.5-flash",
                actif=True,
                position=10,
            )
        )
        await db_session.commit()

        par_id = {m["model"]: m for m in await agent_gratuit.liste_modeles(db_session)}

        assert par_id["glm-4.5-flash"]["role"] == "primaire"
        assert par_id["glm-4.5-flash"]["slug"] == "zai"
        # Plus aucune lane ne porte glm-4.7-flash : le catalogue le dit.
        assert par_id["glm-4.7-flash"]["actif"] is False
        assert par_id["glm-4.7-flash"]["slug"] is None


# ---------------------------------------------------------------------------
# Reaction a un echec fournisseur
# ---------------------------------------------------------------------------


class TestReagir:
    """Ce qu'on fait d'une lane apres un refus, decide par statut HTTP.

    L'ancien code cherchait des sous-chaines (« quota », « http 5 ») dans le
    message : une cle revoquee, un solde vide et un pic de charge recevaient
    tous le meme repos de dix minutes, indefiniment.
    """

    def test_une_cle_refusee_se_distingue_et_se_repose_longtemps(self):
        for statut in (401, 403):
            r = agent_gratuit.reagir(statut, "unauthorized")
            assert r.cle_refusee is True
            assert r.cooldown_minutes == agent_gratuit.COOLDOWN_CLE_MINUTES

    def test_un_quota_repose_le_temps_court(self):
        r = agent_gratuit.reagir(429, "rate limit exceeded")
        assert r.cle_refusee is False
        assert r.cooldown_minutes == agent_gratuit.COOLDOWN_MINUTES

    def test_une_panne_amont_repose_le_temps_court(self):
        assert agent_gratuit.reagir(503, "bad gateway").cooldown_minutes == (
            agent_gratuit.COOLDOWN_MINUTES
        )

    def test_une_demande_refusee_ne_touche_pas_a_la_lane(self):
        """Modele inconnu, requete malformee, contenu filtre : la lane est saine.

        La mettre au repos masquerait derriere « fournisseur indisponible » une
        erreur que le createur doit voir pour la corriger.
        """
        for statut, message in (
            (400, "invalid model"),
            (404, "not found"),
            (200, "content filter"),
        ):
            r = agent_gratuit.reagir(statut, message)
            assert r.cooldown_minutes is None, (statut, message)
            assert r.cle_refusee is False

    def test_sans_statut_ni_motif_reconnu_la_lane_est_epargnee(self):
        """Une exception de Philum ne doit pas passer pour une panne amont."""
        assert agent_gratuit.reagir(None, "KeyError: 'usage'").cooldown_minutes is None

    def test_sans_statut_mais_avec_motif_la_lane_se_repose(self):
        """Le statut ne survit pas toujours au trajet ; le motif, si."""
        r = agent_gratuit.reagir(None, "Le fournisseur refuse : quota atteint.")
        assert r.cooldown_minutes == agent_gratuit.COOLDOWN_MINUTES
