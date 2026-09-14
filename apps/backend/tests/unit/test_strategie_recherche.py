"""L'arbitre choisit les approches de recherche selon la question, sur tout sujet."""

from __future__ import annotations

from app.services.strategie_recherche import bloc_strategie, familles_de_recherche, strategie


def _noms(question, sous_questions=None, *, web=True, passages=True):
    return [
        a.nom
        for a in strategie(
            question, sous_questions or [], web_disponible=web, passages_disponibles=passages
        )
    ]


def test_une_question_biomedicale_cherche_d_abord_dans_la_litterature():
    noms = _noms("Quelles sont les causes de l'endométriose ?")
    assert noms[0] == "corpus_philum"
    assert noms.index("litterature") < noms.index("web")
    assert "biomedical" in noms and "citants" in noms and "references" in noms


def test_une_question_d_actualite_cherche_d_abord_sur_le_web():
    noms = _noms("Que change la nouvelle loi sur le logement votée en 2026 ?")
    assert noms.index("web") < noms.index("litterature")
    assert "fraicheur" in noms
    assert "biomedical" not in noms


def test_une_question_d_histoire_large_appelle_des_perspectives():
    noms = _noms("Pourquoi la Révolution française éclate-t-elle en 1789 ?")
    assert "perspectives" in noms
    assert "biomedical" not in noms and "passages" not in noms
    assert "litterature" in noms


def test_une_question_debattue_cherche_la_contradiction():
    noms = _noms("La taxe carbone est-elle vraiment efficace ?")
    assert "contradiction" in noms and "citants" in noms


def test_sans_moteur_web_ni_cle_semantic_scholar_ces_approches_disparaissent():
    noms = _noms(
        "Quel est le mécanisme de la résistance aux antibiotiques ?", web=False, passages=False
    )
    assert "web" not in noms and "passages" not in noms and "fraicheur" not in noms
    assert "litterature" in noms


def test_aucune_approche_n_est_repetee_et_chacune_a_sa_raison():
    approches = strategie(
        "Quels sont les effets des pesticides sur les insectes pollinisateurs en 2026 ?",
        [
            "Quel effet mesuré ?",
            "Quelles controverses ?",
            "Quel cadre juridique ?",
            "Quelle histoire ?",
        ],
        web_disponible=True,
        passages_disponibles=True,
    )
    noms = [a.nom for a in approches]
    assert len(noms) == len(set(noms))
    assert all(a.raison for a in approches)
    assert familles_de_recherche(approches)[0] == "corpus_philum"
    assert "Stratégie de recherche retenue" in bloc_strategie(approches)
