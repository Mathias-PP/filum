"""Le reclasseur affine l'ordre des passages, et ne bloque jamais la recherche."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import get_settings
from app.extractors.recherche_litterature import Candidate
from app.services import reclassement
from app.services.recherche_approfondie import REPONSE, Passage, SourceTrouvee, _reclasser


def _transport(monkeypatch, gestionnaire):
    vrai = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(gestionnaire)
        return vrai(*args, **kwargs)

    monkeypatch.setattr(reclassement.httpx, "AsyncClient", client)


@pytest.fixture
def cle(monkeypatch):
    monkeypatch.setattr(get_settings(), "jina_api_key", "cle-de-test")


@pytest.mark.asyncio
async def test_sans_cle_rien_n_est_reclasse(monkeypatch):
    monkeypatch.setattr(get_settings(), "jina_api_key", "")
    assert await reclassement.reclasser("question", ["a"]) is None


@pytest.mark.asyncio
async def test_les_scores_reviennent_dans_l_ordre_des_passages_meme_par_lots(cle, monkeypatch):
    corps: list[dict] = []

    def gestionnaire(requete):
        charge = json.loads(requete.content)
        corps.append(charge)
        assert requete.headers["Authorization"] == "Bearer cle-de-test"
        n = len(charge["documents"])
        # Le service rend les resultats tries par pertinence, pas dans l'ordre.
        resultats = [{"index": i, "relevance_score": i / 100} for i in reversed(range(n))]
        return httpx.Response(200, json={"results": resultats})

    _transport(monkeypatch, gestionnaire)
    monkeypatch.setattr(reclassement, "_TAILLE_LOT", 2)
    scores = await reclassement.reclasser("question", ["a", "b", "c"])

    assert scores == [0.0, 0.01, 0.0]
    assert [len(c["documents"]) for c in corps] == [2, 1]
    assert corps[0]["model"] == reclassement.MODELE_RECLASSEMENT


@pytest.mark.asyncio
async def test_une_reponse_incomplete_ne_rend_rien(cle, monkeypatch):
    _transport(
        monkeypatch,
        lambda r: httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 1}]}),
    )
    assert await reclassement.reclasser("question", ["a", "b"]) is None


@pytest.mark.asyncio
async def test_une_reponse_en_erreur_ne_rend_rien(cle, monkeypatch):
    _transport(monkeypatch, lambda r: httpx.Response(429, json={"detail": "quota"}))
    assert await reclassement.reclasser("question", ["a"]) is None


def _source(url: str, *passages: tuple[str, float]) -> SourceTrouvee:
    return SourceTrouvee(
        candidate=Candidate(url=url, titre=None, famille="web"),
        url_lue=url,
        passages=[Passage(t, REPONSE, s, question="q") for t, s in passages],
        tour=1,
        texte_complet=True,
    )


@pytest.mark.asyncio
async def test_le_reclasseur_change_l_ordre_des_sources(cle, monkeypatch):
    async def juge(question, textes):
        return [0.9 if "decisif" in t else 0.1 for t in textes]

    monkeypatch.setattr(reclassement, "reclasser", juge)
    proche = _source("https://a.test/proche", ("proche par le sens", 0.9))
    decisive = _source("https://a.test/decisive", ("passage decisif", 0.7))

    rendu = await _reclasser([proche, decisive])

    assert rendu == reclassement.MODELE_RECLASSEMENT
    assert decisive.meilleur > proche.meilleur
    assert decisive.en_dict()["passages"][0]["pertinence"] == 0.9


@pytest.mark.asyncio
async def test_un_echec_du_reclasseur_laisse_l_ordre_par_le_sens(cle, monkeypatch):
    async def panne(question, textes):
        return None

    monkeypatch.setattr(reclassement, "reclasser", panne)
    source = _source("https://a.test/a", ("texte", 0.8))
    assert "indisponible" in await _reclasser([source])
    assert source.passages[0].pertinence is None and source.meilleur == 0.8
