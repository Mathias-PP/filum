"""Les renvois du bilan ne citent que des extraits de la fiche, et deviennent des liens."""

from __future__ import annotations

from app.services.citations_bilan import lier_renvois

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
INVENTE = "99999999-9999-4999-8999-999999999999"
FICHE = "https://philum.test/@moi/taxe"


def test_chaque_extrait_garde_son_numero_et_devient_un_lien():
    texte = f"Premier fait. [extrait:{A}] Second fait. [extrait:{B}] [extrait:{A}]"
    lie = lier_renvois(texte, {A, B}, FICHE)

    assert lie.cites == 2 and lie.retires == 0
    assert f"Premier fait. [1]({FICHE}#extrait-{A})" in lie.texte
    assert f"Second fait. [2]({FICHE}#extrait-{B}) [1]({FICHE}#extrait-{A})" in lie.texte
    assert "[extrait:" not in lie.texte


def test_un_renvoi_vers_rien_est_retire_et_la_reponse_le_dit():
    lie = lier_renvois(f"Inventé. [extrait:{INVENTE}]", {A}, FICHE)
    assert INVENTE not in lie.texte
    assert lie.texte.startswith("Inventé.")
    assert "1 renvoi retiré" in lie.texte


def test_un_texte_sans_renvoi_reste_intact():
    assert lier_renvois("Rien à citer.", {A}, FICHE).texte == "Rien à citer."
