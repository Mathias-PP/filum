"""Ordonnanceur d'enrichissement : garde-fou anti-doublon et etancheite.

Les deux verifications partagent une passe. Il faut donc qu'aucune ne puisse
emporter l'autre, et qu'une fiche publique servie en boucle ne relance pas
indefiniment le meme travail.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.extractors.open_access import OpenAccessResult, OpenAccessStatus
from app.extractors.retraction import RetractionResult, RetractionStatus
from app.services import source_enrichment as se


class TestSchedule:
    """Une fiche publique populaire est servie des dizaines de fois par minute,
    et relancerait le meme enrichissement a chaque requete tant que le premier
    n'a pas commit."""

    def test_une_source_deja_en_vol_n_est_pas_replanifiee(self, monkeypatch):
        spawned: list[list] = []
        monkeypatch.setattr(se.asyncio, "create_task", lambda coro: (coro.close(), _Noop())[1])
        monkeypatch.setattr(se, "_run", lambda pairs: spawned.append(pairs) or _coro())

        sid = uuid4()
        se.schedule_source_enrichment([(sid, "10.1/x")])
        se.schedule_source_enrichment([(sid, "10.1/x")])

        assert len(spawned) == 1
        se._in_flight.discard(sid)

    def test_liste_vide_ne_planifie_rien(self, monkeypatch):
        called: list[int] = []
        monkeypatch.setattr(se.asyncio, "create_task", lambda coro: called.append(1))
        se.schedule_source_enrichment([])
        assert called == []


class TestEnrichOne:
    @pytest.mark.asyncio
    async def test_les_deux_verdicts_sont_ecrits_ensemble(self, monkeypatch):
        monkeypatch.setattr(
            se, "check_retraction", _returns(RetractionResult(status=RetractionStatus.NONE))
        )
        monkeypatch.setattr(
            se,
            "check_open_access",
            _returns(OpenAccessResult(status=OpenAccessStatus.GOLD, url="https://x/a")),
        )
        values = await se._enrich_one("10.1/x")
        assert values["retraction_status"] == "none"
        assert values["oa_status"] == "gold"
        assert values["oa_url"] == "https://x/a"
        assert values["retraction_checked_at"] == values["oa_checked_at"]

    @pytest.mark.asyncio
    async def test_une_panne_d_openalex_ne_prive_pas_du_badge_de_retractation(self, monkeypatch):
        # Sans etancheite, une panne d'un service ferait disparaitre le verdict
        # de l'autre, alors qu'il a bien ete obtenu.
        monkeypatch.setattr(
            se,
            "check_retraction",
            _returns(RetractionResult(status=RetractionStatus.RETRACTED, notice_doi="10.1/r")),
        )
        monkeypatch.setattr(se, "check_open_access", _raises())
        values = await se._enrich_one("10.1/x")
        assert values["retraction_status"] == "retracted"
        assert "oa_status" not in values

    @pytest.mark.asyncio
    async def test_une_panne_de_crossref_ne_prive_pas_du_lien_libre(self, monkeypatch):
        monkeypatch.setattr(se, "check_retraction", _raises())
        monkeypatch.setattr(
            se,
            "check_open_access",
            _returns(OpenAccessResult(status=OpenAccessStatus.GREEN, url="https://hal/a")),
        )
        values = await se._enrich_one("10.1/x")
        assert values["oa_url"] == "https://hal/a"
        assert "retraction_status" not in values

    @pytest.mark.asyncio
    async def test_deux_pannes_n_ecrivent_rien(self, monkeypatch):
        # Rien a ecrire vaut mieux qu'ecrire une date de verification pour une
        # verification qui n'a pas eu lieu : la source restera a NULL et sera
        # reprise au prochain affichage.
        monkeypatch.setattr(se, "check_retraction", _raises())
        monkeypatch.setattr(se, "check_open_access", _raises())
        assert await se._enrich_one("10.1/x") == {}


class TestPeremption:
    """Mesure du 2026-08-07 sur les 643 sources publiees : 117 avaient bascule
    en acces ouvert sans que la fiche le dise, et 2 papiers corriges restaient
    affiches « non verifiable ». Cause : le declenchement paresseux ne repechait
    que les verdicts *absents*. Un verdict ecrit une fois ne l'etait pour
    toujours, alors qu'il porte sur un monde qui bouge.
    """

    def test_un_verdict_frais_n_est_pas_reverifie(self):
        assert se.needs_recheck(_days_ago(2), "none", "10.1/x") is False

    def test_un_verdict_vieux_est_reverifie(self):
        assert se.needs_recheck(_days_ago(60), "none", "10.1/x") is True

    def test_un_verdict_absent_est_verifie(self):
        assert se.needs_recheck(None, None, "10.1/x") is True

    def test_un_service_muet_est_repris_bien_plus_tot(self):
        """« Non verifiable » sur une source qui porte un DOI ne dit rien du
        papier : il dit que le service n'a pas repondu. Attendre un mois pour
        redemander laisserait la fiche mentir tout ce temps."""
        assert se.needs_recheck(_days_ago(3), "unverifiable", "10.1/x") is True
        assert se.needs_recheck(_hours_ago(2), "unverifiable", "10.1/x") is False

    def test_sans_doi_rien_ne_peut_changer(self):
        """Aucun service ne sait repondre sans identifiant. Repasser tous les
        mois sur ces 341 sources serait du bruit reseau pur, et le verdict
        « non verifiable » y est definitif, pas provisoire."""
        assert se.needs_recheck(_days_ago(365), "unverifiable", None) is False


def _days_ago(n: int):
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=n)


def _hours_ago(n: int):
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=n)


def _returns(value):
    async def call(doi):
        return value

    return call


def _raises():
    async def call(doi):
        raise OSError("service down")

    return call


class _Noop:
    def add_done_callback(self, cb): ...

    def __hash__(self):
        return 0


async def _coro():
    return None
