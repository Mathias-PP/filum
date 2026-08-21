"""Un fragment de phrase n'est pas un titre, meme faute de mieux.

Le repli sur le texte du lien a ete introduit le 2026-08-07 sur un constat
juste : 6 sources ProPublica sur 11 arrivaient sans titre, plusieurs sites
refusant la visite du backfill, et une source sans titre s'affiche comme une
URL nue. Le texte du lien valait mieux que rien.

L'audit persona du meme jour montre ce que « mieux que rien » donne en
pratique. Sur 102 titres produits pour quatre contenus reels, 15 commencent
par une minuscule, et ce sont des morceaux de phrase souligne :
« at least $3 billion », « ran for president », « targeted right-leaning
nonprofits », « criticized the IRS for loose spending on its conferences. »
Aucun ne nomme un document. Affiches comme titres de source, ils se lisent
comme si l'auteur avait cite un texte portant ce nom.

C'est la regle deja tenue ailleurs dans le projet -- un titre faux est pire
qu'un titre absent (#317 sur `impact_factor`, #323 sur `title='OSF'`) : une
valeur fausse se recopie dans la fiche sans que rien ne signale qu'elle ne
designe pas ce qu'elle pretend designer, sur une plateforme qui promet la
tracabilite. L'URL, elle, reste juste.

La seule exception mesuree est le nom propre a majuscule interne : sur les
15, `iGPT` est le seul vrai titre. `arXiv`, `eLife`, `iPhone` sont du meme
genre et doivent survivre.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints.imports import _fallback_title_from_anchor
from app.services.import_parsers import ImportedRef


def _titre_depuis(ancre: str) -> str | None:
    ref = ImportedRef(url="https://exemple.test/a", raw_text=ancre)
    _fallback_title_from_anchor([ref])
    return ref.title


@pytest.mark.parametrize(
    "ancre",
    [
        "at least $3 billion",
        "ran for president",
        "targeted right-leaning nonprofits",
        "criticized the IRS for loose spending on its conferences.",
        "had also targeted progressive groups",
        "the hardware overhang",
        "stochastic gradient descent",
        "dropout",
    ],
)
def test_un_fragment_de_phrase_ne_devient_pas_un_titre(ancre: str) -> None:
    assert _titre_depuis(ancre) is None


@pytest.mark.parametrize(
    "ancre",
    [
        "The Distribution of Tax Noncompliance",
        "Neural networks and deep learning",
        "Comprehensive Mental Health Action Plan 2013-2030",
        "GBD Results",
        "1984",
        "« Le Monde » du 3 mai",
    ],
)
def test_un_vrai_titre_est_conserve(ancre: str) -> None:
    assert _titre_depuis(ancre) == ancre


@pytest.mark.parametrize("ancre", ["iGPT", "arXiv", "eLife", "iPhone 15 Pro", "ggPlot"])
def test_le_nom_propre_a_majuscule_interne_survit(ancre: str) -> None:
    """`iGPT` etait le seul vrai titre parmi les 15 ancres en minuscule."""
    assert _titre_depuis(ancre) == ancre


def test_un_titre_deja_present_n_est_jamais_touche() -> None:
    ref = ImportedRef(
        url="https://exemple.test/a", title="Titre reel", raw_text="ran for president"
    )
    _fallback_title_from_anchor([ref])
    assert ref.title == "Titre reel"


def test_l_url_reste_intacte_quand_l_ancre_est_refusee() -> None:
    """Le remede ne doit pas coûter la source : seul le titre est retire."""
    ref = ImportedRef(url="https://exemple.test/a", raw_text="ran for president")
    _fallback_title_from_anchor([ref])
    assert ref.url == "https://exemple.test/a"
    assert ref.title is None
