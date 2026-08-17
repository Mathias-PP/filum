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


def test_une_phrase_entiere_est_refusee() -> None:
    """« 2 a 6 mots » dit le prompt, mais le modele rend parfois une phrase.

    Mesuree sur la vitrine : « Chiffre de depart de l'article : la depense
    ne bougeant pas avec l'activite mentale, le sommeil ne peut pas etre une
    simple mise en veille energetique. » etait servie comme titre d'extrait.
    Un intitule sert a *retrouver* dans une liste, pas a *raconter*. Au-dela
    de huit mots, on ne repere plus, on lit.
    """
    phrase = (
        "Chiffre de depart de l'article : la depense ne bougeant pas avec "
        "l'activite mentale, le sommeil ne peut pas etre une simple mise en "
        "veille energetique."
    )
    assert normalize_chunk_titles([phrase, "b", "c"], PASSAGES) == [None, "b", "c"]


def test_un_titre_court_passe() -> None:
    assert normalize_chunk_titles(["Reconsolidation de la memoire", "b", "c"], PASSAGES) == [
        "Reconsolidation de la memoire",
        "b",
        "c",
    ]


def test_huit_mots_juste_au_seuil_passe() -> None:
    """La marge existe : le prompt dit 2-6, on tolere jusqu'a 8 pour ne pas
    rejeter un titre qui contient une preposition ou un article de plus."""
    huit = "Un titre exactement de huit mots ici bien"
    assert len(huit.split()) == 8
    result = normalize_chunk_titles([huit, "b", "c"], PASSAGES)
    assert result[0] == huit


def test_aucun_passage_aucun_intitule() -> None:
    assert normalize_chunk_titles(["a", "b"], []) == []
