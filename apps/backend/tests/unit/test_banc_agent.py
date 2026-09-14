"""Les chiffres du banc d'essai de l'agent, tires des evenements d'un tour."""

from __future__ import annotations

from app.scripts.banc_agent import _tableau, mesurer


def test_mesurer_compte_les_refus_d_extraits_les_jetons_et_les_relances():
    evenements = [
        {"type": "tool_result", "payload": {"name": "add_excerpt", "result": {"error": "absent"}}},
        {"type": "tool_result", "payload": {"name": "add_excerpt", "result": {"id": "e1"}}},
        {"type": "tool_result", "payload": {"name": "web_search", "result": {"results": []}}},
        {"type": "controle_relance", "payload": {"tour": 2}},
        {"type": "done", "payload": {"usage": {"prompt_tokens": 1200, "completion_tokens": 80}}},
    ]
    mesures = mesurer(evenements)
    assert mesures["appels_outils"] == 3
    assert mesures["add_excerpt_refuses"] == 1
    assert mesures["part_extraits_refuses"] == 0.5
    assert mesures["controle_relances"] == 1
    assert mesures["prompt_tokens"] == 1200


def test_sans_extrait_tente_la_part_de_refus_n_existe_pas():
    assert mesurer([])["part_extraits_refuses"] is None


def test_le_tableau_porte_une_ligne_par_demande():
    tableau = _tableau([{"question": "comment prévenir l'arthrose?", "duree_s": 12.5}])
    assert tableau.count("\n") == 2
    assert "12.5" in tableau
