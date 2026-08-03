"""Classification des avis Crossref et garde-fous du verdict « non verifiable »."""

from __future__ import annotations

import pytest

from app.extractors.retraction import (
    RetractionStatus,
    check_retraction,
    classify_updates,
)


class TestClassifyUpdates:
    def test_aucun_avis_est_une_information_positive(self):
        # Crossref connait le DOI et ne signale rien : ce n'est pas « inconnu ».
        assert classify_updates([]).status is RetractionStatus.NONE
        assert classify_updates(None).status is RetractionStatus.NONE

    def test_retractation_simple(self):
        r = classify_updates([{"type": "retraction", "DOI": "10.1016/S0140-6736(10)60175-4"}])
        assert r.status is RetractionStatus.RETRACTED
        assert r.notice_doi == "10.1016/s0140-6736(10)60175-4"

    def test_le_plus_grave_l_emporte_sur_l_ordre_d_arrivee(self):
        # Wakefield 1998 : une correction en 2004, une retractation en 2010.
        # Afficher « corrige » d'un article retracte serait un mensonge.
        r = classify_updates(
            [
                {"type": "correction", "DOI": "10.1/correction"},
                {"type": "retraction", "DOI": "10.1/retraction"},
            ]
        )
        assert r.status is RetractionStatus.RETRACTED
        assert r.notice_doi == "10.1/retraction"

    def test_l_ordre_inverse_donne_le_meme_verdict(self):
        r = classify_updates(
            [
                {"type": "retraction", "DOI": "10.1/retraction"},
                {"type": "correction", "DOI": "10.1/correction"},
            ]
        )
        assert r.status is RetractionStatus.RETRACTED
        assert r.notice_doi == "10.1/retraction"

    @pytest.mark.parametrize(
        "crossref_type",
        ["retraction", "partial_retraction", "withdrawal", "removal"],
    )
    def test_tout_ce_qui_retire_l_article_est_une_retractation(self, crossref_type):
        assert classify_updates([{"type": crossref_type}]).status is RetractionStatus.RETRACTED

    @pytest.mark.parametrize("crossref_type", ["correction", "erratum", "corrigendum"])
    def test_les_variantes_de_correction(self, crossref_type):
        assert classify_updates([{"type": crossref_type}]).status is RetractionStatus.CORRECTED

    def test_mise_en_garde(self):
        assert (
            classify_updates([{"type": "expression_of_concern"}]).status
            is RetractionStatus.CONCERN
        )

    def test_type_inconnu_invite_a_verifier_plutot_que_de_rassurer(self):
        # Crossref peut ajouter des types ; « rien signale » serait alors faux.
        assert classify_updates([{"type": "new_thing_2030"}]).status is RetractionStatus.CONCERN

    def test_entree_sans_type_est_ignoree(self):
        assert classify_updates([{"DOI": "10.1/x"}]).status is RetractionStatus.NONE
        assert classify_updates([{"type": ""}]).status is RetractionStatus.NONE

    def test_casse_et_espaces_du_type(self):
        assert classify_updates([{"type": "  Retraction "}]).status is RetractionStatus.RETRACTED

    def test_avis_sans_doi_reste_un_avis(self):
        r = classify_updates([{"type": "retraction"}])
        assert r.status is RetractionStatus.RETRACTED
        assert r.notice_doi is None


class TestCheckRetraction:
    @pytest.mark.asyncio
    async def test_sans_doi_le_verdict_est_non_verifiable(self):
        # Surtout pas NONE : rien n'a ete verifie.
        assert (await check_retraction(None)).status is RetractionStatus.UNVERIFIABLE
        assert (await check_retraction("   ")).status is RetractionStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_doi_inconnu_de_crossref(self, monkeypatch):
        monkeypatch.setattr(
            "httpx.AsyncClient.get",
            _fake_get(status_code=404, payload={}),
        )
        assert (await check_retraction("10.0/nope")).status is RetractionStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_reseau_muet(self, monkeypatch):
        async def boom(self, url):
            raise OSError("network down")

        monkeypatch.setattr("httpx.AsyncClient.get", boom)
        assert (await check_retraction("10.1/x")).status is RetractionStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_reponse_nominale_sans_avis(self, monkeypatch):
        monkeypatch.setattr(
            "httpx.AsyncClient.get",
            _fake_get(status_code=200, payload={"message": {"DOI": "10.1/x"}}),
        )
        assert (await check_retraction("10.1/x")).status is RetractionStatus.NONE

    @pytest.mark.asyncio
    async def test_reponse_nominale_avec_avis(self, monkeypatch):
        monkeypatch.setattr(
            "httpx.AsyncClient.get",
            _fake_get(
                status_code=200,
                payload={"message": {"updated-by": [{"type": "retraction", "DOI": "10.1/r"}]}},
            ),
        )
        r = await check_retraction("10.1/x")
        assert r.status is RetractionStatus.RETRACTED
        assert r.notice_doi == "10.1/r"

    @pytest.mark.asyncio
    async def test_json_illisible(self, monkeypatch):
        class Broken:
            status_code = 200

            def json(self):
                raise ValueError("not json")

        async def get(self, url):
            return Broken()

        monkeypatch.setattr("httpx.AsyncClient.get", get)
        assert (await check_retraction("10.1/x")).status is RetractionStatus.UNVERIFIABLE


def _fake_get(*, status_code: int, payload: dict):
    class Response:
        def __init__(self):
            self.status_code = status_code

        def json(self):
            return payload

    async def get(self, url):
        return Response()

    return get

