"""Le motif de retractation, du CSV Retraction Watch jusqu'a la source."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.extractors.retraction import RetractionStatus
from app.extractors import retraction_watch as rw

_ENTETE = (
    "Record ID,Title,Subject,Institution,Journal,Publisher,Country,Author,URLS,"
    "ArticleType,RetractionDate,RetractionDOI,RetractionPubMedID,OriginalPaperDate,"
    "OriginalPaperDOI,OriginalPaperPubMedID,RetractionNature,Reason,Paywalled,Notes,"
)


def _ligne(*, doi: str, nature: str, motif: str, date_avis: str) -> str:
    return (
        f"1,Titre,Sujet,Inst,Revue,Editeur,Pays,Auteur,http://x,"
        f'Research Article,{date_avis},10.9/notice,,1/1/2000 0:00,{doi},,{nature},"{motif}",No,,'
    )


class TestParserDump:
    def test_indexe_par_doi_en_minuscules(self):
        csv = (
            _ENTETE
            + "\n"
            + _ligne(
                doi="10.1/ABC",
                nature="Retraction",
                motif="Falsification of Data;",
                date_avis="2/6/2010 0:00",
            )
        )
        index = rw.parser_dump(csv)
        assert list(index) == ["10.1/abc"]
        avis = index["10.1/abc"][0]
        assert avis.statut is RetractionStatus.RETRACTED
        assert avis.motif == "Falsification of Data;"
        assert avis.date_avis == date(2010, 2, 6)

    def test_conserve_tous_les_avis_d_un_meme_article(self):
        """Wakefield : correction en 2004, retractation en 2010. Les deux comptent."""
        csv = "\n".join(
            [
                _ENTETE,
                _ligne(
                    doi="10.1/w", nature="Correction", motif="Error;", date_avis="3/6/2004 0:00"
                ),
                _ligne(
                    doi="10.1/w",
                    nature="Retraction",
                    motif="Falsification;",
                    date_avis="2/6/2010 0:00",
                ),
            ]
        )
        assert len(rw.parser_dump(csv)["10.1/w"]) == 2

    def test_reinstallation_ecartee(self):
        """« Retracte, motif : reinstallation » ne veut rien dire."""
        csv = (
            _ENTETE
            + "\n"
            + _ligne(
                doi="10.1/r", nature="Reinstatement", motif="Notice;", date_avis="1/1/2020 0:00"
            )
        )
        assert rw.parser_dump(csv) == {}

    def test_ligne_sans_doi_ou_sans_motif_ignoree(self):
        csv = "\n".join(
            [
                _ENTETE,
                _ligne(
                    doi="", nature="Retraction", motif="Falsification;", date_avis="1/1/2020 0:00"
                ),
                _ligne(doi="10.1/v", nature="Retraction", motif="", date_avis="1/1/2020 0:00"),
            ]
        )
        assert rw.parser_dump(csv) == {}

    def test_date_illisible_ne_perd_pas_l_avis(self):
        csv = (
            _ENTETE
            + "\n"
            + _ligne(doi="10.1/d", nature="Retraction", motif="Motif;", date_avis="pas une date")
        )
        assert rw.parser_dump(csv)["10.1/d"][0].date_avis is None


class TestMotifPour:
    def _avis(self, statut: RetractionStatus, motif: str, jour: date | None):
        return rw.AvisRetractionWatch(doi="10.1/x", statut=statut, motif=motif, date_avis=jour)

    def test_filtre_sur_le_statut_retenu(self):
        """Le motif d'une correction ne s'affiche pas sous un badge de retractation."""
        avis = [
            self._avis(RetractionStatus.CORRECTED, "Erreur", date(2004, 3, 6)),
            self._avis(RetractionStatus.RETRACTED, "Falsification", date(2010, 2, 6)),
        ]
        assert rw.motif_pour(avis, "retracted") == "Falsification"
        assert rw.motif_pour(avis, "corrected") == "Erreur"

    def test_aucun_avis_de_la_bonne_nature_vaut_silence(self):
        avis = [self._avis(RetractionStatus.CORRECTED, "Erreur", date(2004, 3, 6))]
        assert rw.motif_pour(avis, "retracted") is None

    def test_le_plus_recent_gagne(self):
        avis = [
            self._avis(RetractionStatus.RETRACTED, "Ancien", date(2010, 1, 1)),
            self._avis(RetractionStatus.RETRACTED, "Recent", date(2020, 1, 1)),
        ]
        assert rw.motif_pour(avis, "retracted") == "Recent"

    def test_date_inconnue_ne_supplante_pas_une_date_connue(self):
        avis = [
            self._avis(RetractionStatus.RETRACTED, "Date connue", date(2010, 1, 1)),
            self._avis(RetractionStatus.RETRACTED, "Date inconnue", None),
        ]
        assert rw.motif_pour(avis, "retracted") == "Date connue"

    def test_statut_absent_vaut_silence(self):
        avis = [self._avis(RetractionStatus.RETRACTED, "Falsification", date(2010, 1, 1))]
        assert rw.motif_pour(avis, None) is None


class TestTelecharger:
    @pytest.mark.asyncio
    async def test_service_muet_rend_none_sans_lever(self, monkeypatch):
        async def _boum(*a, **k):
            raise httpx.ConnectError("coupe")

        monkeypatch.setattr(httpx.AsyncClient, "get", _boum)
        assert await rw.telecharger_dump() is None

    @pytest.mark.asyncio
    async def test_reponse_non_200_rend_none(self, monkeypatch):
        async def _cinq_cents(*a, **k):
            return httpx.Response(503, request=httpx.Request("GET", rw._URL))

        monkeypatch.setattr(httpx.AsyncClient, "get", _cinq_cents)
        assert await rw.telecharger_dump() is None

    @pytest.mark.asyncio
    async def test_reponse_valide_est_indexee(self, monkeypatch):
        csv = (
            _ENTETE
            + "\n"
            + _ligne(doi="10.1/ok", nature="Retraction", motif="Motif;", date_avis="1/1/2020 0:00")
        )

        async def _ok(*a, **k):
            return httpx.Response(200, text=csv, request=httpx.Request("GET", rw._URL))

        monkeypatch.setattr(httpx.AsyncClient, "get", _ok)
        index = await rw.telecharger_dump()
        assert index is not None and "10.1/ok" in index
