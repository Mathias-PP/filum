"""Un intitule mal aligne designe le mauvais passage, sans que rien ne le dise.

Le modele rend une liste, les passages en sont une autre. Si l'une est plus
courte, l'appariement par position decale tout ce qui suit : le passage 3
porte l'intitule du 4, et l'auteur·ice n'a aucun moyen de s'en apercevoir sur
un ecran de dix extraits. C'est la faute que ces tests interdisent.

Meme regle qu'en #317, #323 et #327 : mieux vaut pas d'intitule qu'un faux.
"""

from __future__ import annotations

from app.services.llm import normalize_chunk_titles

PASSAGES = ["un", "deux", "trois"]


def test_un_intitule_par_passage() -> None:
    assert len(normalize_chunk_titles(["a", "b", "c"], PASSAGES)) == 3


def test_une_liste_trop_courte_ne_decale_rien() -> None:
    """Les passages non nommes le restent, les autres gardent leur place."""
    assert normalize_chunk_titles(["a"], PASSAGES) == ["a", None, None]


def test_une_liste_trop_longue_est_tronquee() -> None:
    assert normalize_chunk_titles(["a", "b", "c", "d", "e"], PASSAGES) == ["a", "b", "c"]


def test_un_intitule_vide_vaut_absence() -> None:
    assert normalize_chunk_titles(["a", "   ", "c"], PASSAGES) == ["a", None, "c"]


def test_un_intitule_demesure_est_borne() -> None:
    """La colonne fait 200 caracteres : au-dela l'ecriture echouerait."""
    titres = normalize_chunk_titles(["x" * 500, "b", "c"], PASSAGES)
    assert titres[0] is not None
    assert len(titres[0]) <= 200


def test_aucun_passage_aucun_intitule() -> None:
    assert normalize_chunk_titles(["a", "b"], []) == []
