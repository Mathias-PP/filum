"""Coercition des arguments d'outil rendus par le modèle.

Un fournisseur rend les arguments d'appel en JSON, et le JSON qu'écrit un
modèle ne respecte pas toujours le type annoncé par le schéma : `limit` part
en `"10"`, un booléen en `"true"`, une liste en chaîne JSON. Passés tels
quels, ces arguments faisaient lever la fonction outil loin de son entrée,
avec un message que le modèle ne pouvait pas relier au paramètre fautif.
Mesuré en production : `search_cards a échoué : '>' not supported between
instances of 'int' and 'str'`, suivi de plusieurs tours de boucle.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agent_tools.philum import _coercer, philum_tools

SCHEMA = {
    "limit": {"type": "integer"},
    "query": {"type": "string"},
    "published": {"type": "boolean"},
    "tags": {"type": "array", "items": {"type": "string"}},
    "sources": {"type": "array", "items": {"type": "object"}},
    "meta": {"type": "object"},
}


class TestEntiers:
    def test_chaine_numerique_devient_un_entier(self):
        assert _coercer({"limit": "10"}, SCHEMA) == {"limit": 10}

    def test_espaces_autour_du_nombre(self):
        assert _coercer({"limit": " 7 "}, SCHEMA) == {"limit": 7}

    def test_flottant_entier_passe(self):
        assert _coercer({"limit": 10.0}, SCHEMA) == {"limit": 10}

    def test_flottant_non_entier_refuse(self):
        with pytest.raises(ValueError, match="limit"):
            _coercer({"limit": 10.5}, SCHEMA)

    def test_texte_non_numerique_refuse_en_nommant_le_parametre(self):
        with pytest.raises(ValueError) as exc:
            _coercer({"limit": "beaucoup"}, SCHEMA)
        assert "limit" in str(exc.value)
        assert "entier" in str(exc.value)

    def test_un_booleen_n_est_pas_un_entier(self):
        # `True` vaut 1 en Python : sans garde, `limit=true` passerait pour 1.
        with pytest.raises(ValueError, match="limit"):
            _coercer({"limit": True}, SCHEMA)


class TestBooleens:
    @pytest.mark.parametrize(
        ("brut", "attendu"),
        [("true", True), ("True", True), ("false", False), ("FALSE", False)],
    )
    def test_chaines_booleennes(self, brut, attendu):
        assert _coercer({"published": brut}, SCHEMA) == {"published": attendu}

    def test_chaine_ambigue_refusee(self):
        with pytest.raises(ValueError, match="published"):
            _coercer({"published": "peut-etre"}, SCHEMA)


class TestListesEtObjets:
    def test_liste_serialisee_en_json(self):
        assert _coercer({"tags": '["a", "b"]'}, SCHEMA) == {"tags": ["a", "b"]}

    def test_objet_serialise_en_json(self):
        assert _coercer({"meta": '{"k": 1}'}, SCHEMA) == {"meta": {"k": 1}}

    def test_liste_de_dicts_serialisee(self):
        args = {"sources": '[{"url": "https://a.example"}]'}
        assert _coercer(args, SCHEMA) == {"sources": [{"url": "https://a.example"}]}

    def test_chaine_qui_n_est_pas_du_json_refusee(self):
        with pytest.raises(ValueError, match="tags"):
            _coercer({"tags": "a, b"}, SCHEMA)

    def test_json_valide_du_mauvais_type_refuse(self):
        with pytest.raises(ValueError, match="tags"):
            _coercer({"tags": '{"a": 1}'}, SCHEMA)


class TestNonRegression:
    def test_les_valeurs_deja_du_bon_type_ne_bougent_pas(self):
        args = {
            "limit": 10,
            "query": "warburg",
            "published": True,
            "tags": ["a"],
            "meta": {"k": 1},
        }
        assert _coercer(args, SCHEMA) == args

    def test_une_chaine_reste_une_chaine(self):
        # Un titre numerique est un titre : ne pas le convertir en entier.
        assert _coercer({"query": "2026"}, SCHEMA) == {"query": "2026"}

    def test_null_traverse_sans_coercition(self):
        # Un parametre optionnel explicitement nul doit atteindre la fonction.
        assert _coercer({"limit": None}, SCHEMA) == {"limit": None}

    def test_parametre_hors_schema_traverse(self):
        # La validation des inconnus se fait ailleurs, avant l'appel.
        assert _coercer({"autre": "x"}, SCHEMA) == {"autre": "x"}


class TestBoutEnBout:
    """L'incident tel qu'il s'est produit, rejoue au travers de l'outil."""

    @pytest.mark.asyncio
    async def test_search_cards_accepte_une_limite_en_chaine(self):
        vues: dict[str, object] = {}

        # Meme signature que la vraie : le schema de l'outil en est derive.
        async def faux_search_cards(db, query: str, limit: int = 10):
            """Cherche des fiches."""
            vues.update({"query": query, "limit": limit})
            return []

        with patch("app.agent_tools.philum.lecture.search_cards", faux_search_cards):
            outil = next(o for o in philum_tools() if o.name == "search_cards")
            resultat = await outil.execute(
                SimpleNamespace(db=None, user=None, creator_id=None),
                {"query": "warburg", "limit": "10"},
            )

        assert "error" not in resultat
        assert vues["limit"] == 10

    @pytest.mark.asyncio
    async def test_une_limite_illisible_nomme_le_parametre(self):
        outil = next(o for o in philum_tools() if o.name == "search_cards")
        resultat = await outil.execute(
            SimpleNamespace(db=None, user=None, creator_id=None),
            {"query": "warburg", "limit": "beaucoup"},
        )
        assert "limit" in resultat["error"]
        assert "entier" in resultat["error"]
