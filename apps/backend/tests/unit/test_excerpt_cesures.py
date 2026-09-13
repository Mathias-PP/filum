"""Un mot coupe en fin de ligne ne doit pas faire refuser une citation exacte.

Mesure du 2026-09-13 : un PDF de recommandations portait « démo-graphiques »,
coupe en fin de ligne. Le passage cite d'un seul tenant a ete refuse cinq fois
alors qu'il figurait mot pour mot dans la source.
"""

from __future__ import annotations

from app.services.excerpt_anchor import Selecteurs, ancrer

PAGE_PDF = (
    "Introduction du rapport.\n"
    "Les facteurs démo-\n"
    "graphiques expliquent la hausse des cas. "
    "La suite du rapport traite des traitements."
)


def _chercher(page: str, citation: str):
    return ancrer(page, Selecteurs(quote=citation, prefix="", suffix="", offset=None))


def test_une_cesure_de_fin_de_ligne_est_recollee():
    ancrage = _chercher(PAGE_PDF, "Les facteurs démographiques expliquent la hausse des cas.")
    assert ancrage is not None
    assert ancrage.exact
    # Les offsets designent le texte reel, cesure comprise.
    assert ancrage.texte == "Les facteurs démo-\ngraphiques expliquent la hausse des cas."


def test_un_tiret_conditionnel_est_ignore():
    page = "Une infor­mation retenue brievement."
    ancrage = _chercher(page, "Une information retenue brievement.")
    assert ancrage is not None
    assert ancrage.exact


def test_la_citation_qui_porte_la_cesure_reste_retrouvee():
    ancrage = _chercher(PAGE_PDF, "Les facteurs démo- graphiques expliquent")
    assert ancrage is not None
    assert ancrage.exact


def test_un_trait_d_union_ordinaire_n_est_pas_retire():
    page = "Le rapport cite une étude franco-allemande récente."
    ancrage = _chercher(page, "une étude franco-allemande récente")
    assert ancrage is not None
    assert ancrage.texte == "une étude franco-allemande récente"
