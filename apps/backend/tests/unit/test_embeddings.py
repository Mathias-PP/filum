from __future__ import annotations

import math

import pytest

from app.models.excerpt_embedding import EMBEDDING_DIM
from app.models.source_excerpt import SourceExcerpt
from app.services import embeddings as module_embeddings
from app.services.embeddings import (
    embed,
    empreinte,
    texte_a_embedder,
    tronquer_et_normaliser,
    url_embeddings,
)


class TestUrlEmbeddings:
    def test_hote_nu_recoit_le_prefixe_v1(self):
        assert url_embeddings("http://litellm:4000") == "http://litellm:4000/v1/embeddings"

    def test_racine_avec_chemin_ne_le_recoit_pas(self):
        base = "https://generativelanguage.googleapis.com/v1beta/openai"
        assert url_embeddings(base) == f"{base}/embeddings"

    def test_barre_finale_ignoree(self):
        assert url_embeddings("http://litellm:4000/") == "http://litellm:4000/v1/embeddings"


class TestTexteAEmbedder:
    def test_joint_intitule_situation_et_verbatim(self):
        e = SourceExcerpt(
            text="Le cerveau consomme 20 % de l'oxygène au repos.",
            title="Coût énergétique",
            context="Introduction d'une revue sur le métabolisme cérébral.",
        )
        assert texte_a_embedder(e) == (
            "Coût énergétique\n"
            "Introduction d'une revue sur le métabolisme cérébral.\n"
            "Le cerveau consomme 20 % de l'oxygène au repos."
        )

    def test_champs_absents_ne_laissent_pas_de_lignes_vides(self):
        e = SourceExcerpt(text="Un verbatim seul.", title=None, context=None)
        assert texte_a_embedder(e) == "Un verbatim seul."

    def test_champs_blancs_traites_comme_absents(self):
        e = SourceExcerpt(text="Un verbatim seul.", title="   ", context="")
        assert texte_a_embedder(e) == "Un verbatim seul."

    def test_texte_tres_long_est_borne(self):
        e = SourceExcerpt(text="a" * 20_000, title=None, context=None)
        assert len(texte_a_embedder(e)) == 8_000


class TestEmpreinte:
    def test_stable_pour_le_meme_texte(self):
        assert empreinte("bonjour") == empreinte("bonjour")

    def test_change_au_moindre_ecart(self):
        assert empreinte("bonjour") != empreinte("bonjour ")

    def test_longueur_sha256(self):
        assert len(empreinte("bonjour")) == 64


class TestTronquerEtNormaliser:
    def test_ramene_a_la_dimension_cible(self):
        assert len(tronquer_et_normaliser([1.0] * 3072)) == EMBEDDING_DIM

    def test_vecteur_rendu_de_norme_un(self):
        v = tronquer_et_normaliser([float(i) for i in range(3072)])
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)

    def test_vecteur_plus_court_que_la_cible_est_garde_entier(self):
        v = tronquer_et_normaliser([3.0, 4.0])
        assert v == pytest.approx([0.6, 0.8])

    def test_vecteur_nul_ne_divise_pas_par_zero(self):
        assert tronquer_et_normaliser([0.0, 0.0]) == [0.0, 0.0]

    def test_troncature_avant_normalisation(self):
        # Si l'ordre etait inverse, la norme porterait sur les dimensions
        # jetees et le vecteur rendu ne serait pas unitaire.
        v = tronquer_et_normaliser([3.0, 4.0, 100.0], dim=2)
        assert v == pytest.approx([0.6, 0.8])


class _ReponseFactice:
    def __init__(self, charge: dict):
        self.status_code = 200
        self.text = ""
        self._charge = charge

    def json(self) -> dict:
        return self._charge


class _ClientFactice:
    def __init__(self, charge: dict):
        self._charge = charge

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, *_args, **_kwargs):
        return _ReponseFactice(self._charge)


def _brancher(monkeypatch, charge: dict) -> None:
    monkeypatch.setattr(
        module_embeddings.httpx,
        "AsyncClient",
        lambda **_: _ClientFactice(charge),
    )

    class _Settings:
        litellm_base_url = "https://exemple.test/v1beta/openai"
        litellm_master_key = "cle"
        embedding_model = "modele"

    monkeypatch.setattr(module_embeddings, "get_settings", lambda: _Settings())


class TestEmbed:
    @pytest.mark.asyncio
    async def test_index_absent_traite_comme_la_position(self, monkeypatch):
        # Gemini serialise en protobuf et elide les valeurs egales au defaut :
        # le premier element d'un lot n'a jamais de champ `index`. Exiger la
        # cle faisait echouer tout appel, donc toute l'indexation.
        _brancher(
            monkeypatch,
            {
                "data": [
                    {"object": "embedding", "embedding": [1.0, 0.0]},
                    {"object": "embedding", "index": 1, "embedding": [0.0, 2.0]},
                ]
            },
        )
        vecteurs = await embed(["premier", "second"])
        assert vecteurs == [[1.0, 0.0], [0.0, 1.0]]

    @pytest.mark.asyncio
    async def test_ordre_retabli_par_index(self, monkeypatch):
        _brancher(
            monkeypatch,
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 2.0]},
                    {"index": 0, "embedding": [3.0, 0.0]},
                ]
            },
        )
        assert await embed(["premier", "second"]) == [[1.0, 0.0], [0.0, 1.0]]

    @pytest.mark.asyncio
    async def test_lot_incomplet_rend_none(self, monkeypatch):
        _brancher(monkeypatch, {"data": [{"embedding": [1.0, 0.0]}]})
        assert await embed(["premier", "second"]) is None
