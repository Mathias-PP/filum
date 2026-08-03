"""Verdict d'acces libre OpenAlex et garde-fous du « non verifiable »."""

from __future__ import annotations

import pytest

from app.extractors.open_access import (
    OpenAccessStatus,
    check_open_access,
    classify_open_access,
)


def _work(**oa):
    return {"open_access": oa}


class TestClassifyOpenAccess:
    def test_ferme_est_une_information_positive(self):
        # OpenAlex connait la reference et ne trouve rien de gratuit : ce n'est
        # pas « inconnu », c'est un fait datable.
        r = classify_open_access(_work(is_oa=False, oa_status="closed", oa_url=None))
        assert r.status is OpenAccessStatus.CLOSED
        assert r.url is None

    def test_libre_donne_une_url_actionnable(self):
        r = classify_open_access(_work(is_oa=True, oa_status="gold", oa_url="https://x.org/a.pdf"))
        assert r.status is OpenAccessStatus.GOLD
        assert r.url == "https://x.org/a.pdf"

    @pytest.mark.parametrize("route", ["diamond", "gold", "green", "hybrid", "bronze"])
    def test_les_routes_connues_sont_nommees(self, route):
        r = classify_open_access(_work(is_oa=True, oa_status=route, oa_url="https://x/a"))
        assert r.status.value == route

    def test_une_route_inconnue_reste_un_acces_libre(self):
        # OpenAlex peut nommer une nouvelle voie : « ferme » serait faux, et
        # priverait le lecteur d'une version gratuite qui existe.
        r = classify_open_access(_work(is_oa=True, oa_status="platinum", oa_url="https://x/a"))
        assert r.status is OpenAccessStatus.OPEN
        assert r.url == "https://x/a"

    def test_reponse_muette_sur_l_acces(self):
        assert classify_open_access({}).status is OpenAccessStatus.UNVERIFIABLE
        assert classify_open_access(None).status is OpenAccessStatus.UNVERIFIABLE
        assert classify_open_access(_work()).status is OpenAccessStatus.UNVERIFIABLE

    def test_replis_d_url_quand_oa_url_manque(self):
        w = _work(is_oa=True, oa_status="green")
        w["best_oa_location"] = {"pdf_url": "https://hal/a.pdf"}
        assert classify_open_access(w).url == "https://hal/a.pdf"

        w["best_oa_location"] = {"landing_page_url": "https://hal/a"}
        assert classify_open_access(w).url == "https://hal/a"

    def test_un_acces_libre_sans_url_reste_annoncable(self):
        # On ne peut pas ouvrir la version gratuite, mais dire qu'elle existe
        # reste vrai et evite de faire croire a un paywall.
        r = classify_open_access(_work(is_oa=True, oa_status="green"))
        assert r.status is OpenAccessStatus.GREEN
        assert r.url is None

    def test_licence_et_doaj_remontent_quand_ils_sont_connus(self):
        w = _work(is_oa=True, oa_status="gold", oa_url="https://x/a")
        w["best_oa_location"] = {"license": "cc-by", "source": {"is_in_doaj": True}}
        r = classify_open_access(w)
        assert r.license == "cc-by"
        assert r.in_doaj is True

    def test_doaj_inconnu_n_est_pas_un_non(self):
        # `None` = OpenAlex ne dit rien. `False` affirmerait que la revue n'y
        # est pas referencee, ce que personne n'a verifie.
        r = classify_open_access(_work(is_oa=True, oa_status="gold", oa_url="https://x/a"))
        assert r.in_doaj is None

    def test_doaj_reste_lisible_sur_une_reference_fermee(self):
        w = _work(is_oa=False, oa_status="closed")
        w["best_oa_location"] = {"source": {"is_in_doaj": False}}
        r = classify_open_access(w)
        assert r.status is OpenAccessStatus.CLOSED
        assert r.in_doaj is False

    def test_casse_et_espaces_du_statut(self):
        r = classify_open_access(_work(is_oa=True, oa_status="  Gold ", oa_url="https://x/a"))
        assert r.status is OpenAccessStatus.GOLD


class TestCheckOpenAccess:
    @pytest.mark.asyncio
    async def test_sans_doi_le_verdict_est_non_verifiable(self):
        assert (await check_open_access(None)).status is OpenAccessStatus.UNVERIFIABLE
        assert (await check_open_access("   ")).status is OpenAccessStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_doi_inconnu_d_openalex(self, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient.get", _fake_get(status_code=404, payload={}))
        assert (await check_open_access("10.0/nope")).status is OpenAccessStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_reseau_muet(self, monkeypatch):
        async def boom(self, url):
            raise OSError("network down")

        monkeypatch.setattr("httpx.AsyncClient.get", boom)
        assert (await check_open_access("10.1/x")).status is OpenAccessStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_reponse_nominale(self, monkeypatch):
        monkeypatch.setattr(
            "httpx.AsyncClient.get",
            _fake_get(
                status_code=200,
                payload={
                    "open_access": {
                        "is_oa": True,
                        "oa_status": "gold",
                        "oa_url": "https://x/a.pdf",
                    }
                },
            ),
        )
        r = await check_open_access("10.1/x")
        assert r.status is OpenAccessStatus.GOLD
        assert r.url == "https://x/a.pdf"

    @pytest.mark.asyncio
    async def test_json_illisible(self, monkeypatch):
        class Broken:
            status_code = 200

            def json(self):
                raise ValueError("not json")

        async def get(self, url):
            return Broken()

        monkeypatch.setattr("httpx.AsyncClient.get", get)
        assert (await check_open_access("10.1/x")).status is OpenAccessStatus.UNVERIFIABLE


def _fake_get(*, status_code: int, payload: dict):
    class Response:
        def __init__(self):
            self.status_code = status_code

        def json(self):
            return payload

    async def get(self, url):
        return Response()

    return get
