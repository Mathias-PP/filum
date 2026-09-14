"""Les candidates de plusieurs moteurs fusionnent en une liste classee et dedoublonnee."""

from __future__ import annotations

from app.extractors.recherche_litterature import Candidate
from app.services.fusion_candidates import fusionner, identite


def _c(url, famille="web", source="tavily", **champs):
    return Candidate(
        url=url, titre=champs.pop("titre", url), famille=famille, sources=[source], **champs
    )


def test_la_meme_source_sous_deux_adresses_n_apparait_qu_une_fois():
    doi = _c("https://doi.org/10.1000/xyz", famille="litterature", source="openalex", citations=12)
    editeur = _c("https://editeur.example/article/10.1000/xyz", source="brave")
    assert identite(doi) == identite(editeur)
    fusion = fusionner([[doi], [editeur]])
    assert len(fusion) == 1
    assert fusion[0].sources == ["openalex", "brave"]
    assert fusion[0].citations == 12


def test_une_source_que_plusieurs_moteurs_placent_haut_passe_devant():
    a, b, c = (_c(f"https://site.example/{n}") for n in "abc")
    fusion = fusionner([[a, b, c], [_c("https://site.example/c", source="brave"), b]])
    urls = [x.url for x in fusion]
    # b et c sont vues par les deux moteurs, a par un seul, meme premiere chez lui.
    assert set(urls[:2]) == {"https://site.example/b", "https://site.example/c"}
    assert urls[-1] == "https://site.example/a"


def test_une_liste_vide_ne_casse_rien():
    assert fusionner([[], []]) == []
