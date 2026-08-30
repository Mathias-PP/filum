"""Le rang reciproque : ce qu'il recompense, et ce qu'il ignore."""

from __future__ import annotations

from app.services.fusion_rangs import K_RANG, fusionner


def test_recompense_l_accord_des_deux_jambes():
    """Deuxieme partout bat premier d'une seule liste.

    C'est tout l'interet de la methode : deux mesures independantes qui
    designent le meme extrait en disent plus long qu'une seule tres sure.
    """
    fusion = fusionner({"sens": ["a", "accord"], "mots": ["b", "accord"]})

    assert [f.identifiant for f in fusion][0] == "accord"
    assert fusion[0].score == 2 / (K_RANG + 2)


def test_une_jambe_vide_ne_derange_pas_l_autre():
    """La recherche par le sens est indisponible sans service d'embeddings."""
    fusion = fusionner({"sens": [], "mots": ["x", "y", "z"]})

    assert [f.identifiant for f in fusion] == ["x", "y", "z"]


def test_nomme_les_jambes_qui_ont_trouve():
    fusion = fusionner({"sens": ["deux", "sens_seul"], "mots": ["deux", "mots_seul"]})
    par_id = {f.identifiant: f.jambes for f in fusion}

    assert par_id["deux"] == frozenset({"sens", "mots"})
    assert par_id["sens_seul"] == frozenset({"sens"})
    assert par_id["mots_seul"] == frozenset({"mots"})


def test_l_ordre_est_stable_a_egalite():
    """A score egal, l'ordre suit la premiere jambe qui a vu l'identifiant."""
    fusion = fusionner({"sens": ["premier"], "mots": ["second"]})

    assert [f.identifiant for f in fusion] == ["premier", "second"]


def test_aucune_jambe_ne_rend_rien():
    assert fusionner({}) == []
