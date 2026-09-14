"""Les mesures du banc de recherche : rappel contre les references d'une revue."""

from __future__ import annotations

from app.scripts.banc_recherche import mesures, question_depuis_revue, tableau


def test_le_rappel_distingue_ce_qui_est_rendu_ce_qui_est_en_tete_et_ce_qui_a_ete_vu():
    reference = ["10.1/a", "https://doi.org/10.1/B", "10.1/c", "10.1/d"]
    trouvees = ["10.1/x", "10.1/a", "10.1/y", "10.1/z", "10.1/b"]
    vues = {"10.1/a", "10.1/b", "10.1/c", "10.1/x"}

    m = mesures(reference, trouvees, vues)

    assert m["reference"] == 4
    assert m["rappel"] == 0.5
    assert m["rappel_aux_r_premieres"] == 0.25
    assert m["rappel_de_la_collecte"] == 0.75
    assert m["trouvees_hors_reference"] == 3


def test_sans_reference_aucun_rappel_n_est_invente():
    assert mesures([], ["10.1/a"], set())["rappel"] is None


def test_une_revue_sans_doi_ne_devient_pas_une_question():
    assert question_depuis_revue({"id": "https://openalex.org/W1", "display_name": "Revue"}) is None
    question = question_depuis_revue(
        {
            "id": "https://openalex.org/W1",
            "display_name": "  Amyloid   imaging in Alzheimer ",
            "doi": "https://doi.org/10.2214/AJR.24",
            "language": "en",
        }
    )
    assert question == {
        "id": "W1",
        "question": "Amyloid imaging in Alzheimer",
        "doi": "10.2214/ajr.24",
        "annee": None,
        "langue": "en",
    }
    assert tableau([{**question, "rappel": 0.5}]).count("\n") == 2
