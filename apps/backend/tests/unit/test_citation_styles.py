"""Une reference mal formee se repere ; une reference bien formee et fausse, non.

Ces tests portent moins sur la typographie exacte de chaque style — elle varie
d'une edition a l'autre, et Philum ne pretend pas remplacer un processeur CSL —
que sur les deux proprietes qui comptent quel que soit le style :

1. **Rien n'est invente.** Une source sans annee, sans auteur ou sans revue ne
   recoit pas de valeur plausible pour completer le gabarit. Elle porte la
   marque d'absence du style, ou omet le segment.
2. **Rien n'est perdu.** Le titre et le lien survivent dans les six styles :
   ce sont les deux seules choses qui permettent au lecteur de retrouver le
   document, et une bibliographie qui les egare ne sert a rien.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models.source import Source
from app.services.citation_styles import STYLES, format_bibliography, format_reference


def _source(**kw) -> Source:
    champs = {
        "url": "https://example.org/a",
        "title": "Inhibitory control development",
        "authors": "Adleman N., Menon V.",
        "published_at": datetime(2012, 5, 3),
        "format": "texte",
        "category": "article-scientifique",
        "author_kind": "chercheur",
        "journal": "Neuroimage",
        "volume": "60",
        "pages": "112-120",
        "doi": "10.1016/j.neuroimage.2012.01.001",
    }
    champs.update(kw)
    return Source(**champs)


@pytest.mark.parametrize("style", sorted(STYLES))
def test_titre_et_lien_survivent_a_tous_les_styles(style):
    rendu = format_reference(_source(), style)
    assert "Inhibitory control development" in rendu
    assert "10.1016/j.neuroimage.2012.01.001" in rendu


@pytest.mark.parametrize("style", sorted(STYLES))
def test_aucune_annee_inventee_quand_la_date_manque(style):
    """Une date absente ne doit pas devenir une date plausible.

    Le DOI est retire du cas : `10.1016/j.neuroimage.2012.01.001` contient
    « 2012 » sans rien dire de la date de parution.
    """
    rendu = format_reference(_source(published_at=None, doi=None), style)
    assert "2012" not in rendu
    assert "Inhibitory control development" in rendu


@pytest.mark.parametrize("style", sorted(STYLES))
def test_une_source_nue_reste_citable(style):
    """Sans auteur, sans revue, sans date : il reste un titre et un lien."""
    rendu = format_reference(
        _source(authors=None, journal=None, volume=None, pages=None, doi=None, published_at=None),
        style,
    )
    assert "Inhibitory control development" in rendu
    assert "https://example.org/a" in rendu


@pytest.mark.parametrize("style", sorted(STYLES))
def test_sans_titre_l_url_tient_lieu_de_titre(style):
    """Une entree muette n'aide personne : l'URL vaut mieux qu'un blanc."""
    rendu = format_reference(_source(title=None), style)
    assert "https://example.org/a" in rendu


def test_apa_inverse_le_nom_et_abrege_le_prenom():
    # « Famille, Prenom » est la seule ecriture non ambigue : sans virgule,
    # `parse_name` applique la convention occidentale (dernier jeton = famille).
    rendu = format_reference(_source(authors="Adleman, Nathalie"), "apa")
    assert rendu.startswith("Adleman, N. (2012).")


def test_mla_abrege_des_trois_auteurs():
    rendu = format_reference(_source(authors="Adleman N., Menon V., Blasey C."), "mla")
    assert "et al." in rendu
    assert "Blasey" not in rendu


def test_vancouver_n_abrege_qu_au_dela_de_six_auteurs():
    six = ", ".join(f"Nom{i} A." for i in range(1, 7))
    assert "et al." not in format_reference(_source(authors=six), "vancouver")
    sept = six + ", Nom7 A."
    rendu = format_reference(_source(authors=sept), "vancouver")
    assert "et al." in rendu
    assert "Nom7" not in rendu


def test_vancouver_omet_la_ponctuation_des_initiales():
    # Deux auteurs : le separateur qui suit la premiere initiale est une
    # virgule, donc il rend l'absence de point visible. Avec un seul auteur le
    # point final du segment masquerait le cas.
    rendu = format_reference(_source(authors="Adleman, Nathalie; Menon, Vinod"), "vancouver")
    assert "Adleman N, Menon V." in rendu


def test_ieee_numerote_la_bibliographie():
    lignes = format_bibliography([_source(), _source(title="Second")], "ieee")
    assert lignes[0].startswith("[1] ")
    assert lignes[1].startswith("[2] ")


def test_les_autres_styles_ne_numerotent_pas():
    lignes = format_bibliography([_source()], "apa")
    assert not lignes[0].startswith("[1]")


def test_initiales_composees_gardent_le_trait_d_union():
    rendu = format_reference(_source(authors="Dupont, Jean-Marc"), "apa")
    assert "Dupont, J.-M." in rendu


@pytest.mark.parametrize("style", sorted(STYLES))
def test_une_liste_abregee_le_reste_dans_tous_les_styles(style):
    """« et al. » n'est pas un nom, mais c'est une information.

    La retirer sans la remplacer ferait citer « Wiltgen, B. J. » d'un article
    ecrit a plusieurs : une reference bien formee et fausse, exactement ce que
    ces tests existent pour empecher.
    """
    rendu = format_reference(_source(authors="Brian J. Wiltgen et al."), style)
    assert "et al." in rendu
    assert "Wiltgen" in rendu


def test_une_liste_complete_ne_recoit_pas_d_et_al():
    assert "et al." not in format_reference(_source(authors="Adleman N., Menon V."), "apa")


def test_chicago_ne_double_pas_le_point_apres_une_initiale():
    # « Loftus, Elizabeth F.. 2005. » etait servi en production.
    rendu = format_reference(_source(authors="Elizabeth F. Loftus"), "chicago")
    assert "Loftus, Elizabeth F. " in rendu
    assert ".." not in rendu


def test_style_inconnu_leve():
    with pytest.raises(KeyError):
        format_reference(_source(), "zotero-maison")
