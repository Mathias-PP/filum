"""Export RIS — le format que lisent EndNote, Mendeley et Zotero."""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace

from app.services.export import export_bibtex, export_ris

from .test_csl import make_source


def make_card(*sources, title="Ma fiche"):
    return SimpleNamespace(title=title, sources=list(sources))


def tags(ris: str) -> list[str]:
    return [line.split("  - ")[0] for line in ris.splitlines() if "  - " in line]


class TestStructure:
    def test_chaque_reference_est_bornee(self):
        # Sans « ER  - », un lecteur RIS fusionne silencieusement toutes les
        # references en une seule.
        ris = export_ris(make_card(make_source(), make_source()))
        assert ris.count("TY  - ") == 2
        assert ris.count("ER  - ") == 2

    def test_syntaxe_deux_espaces_avant_le_tiret(self):
        # « TY - JOUR » (une seule espace) n'est pas du RIS valide.
        ris = export_ris(make_card(make_source()))
        for line in ris.splitlines():
            if line.strip():
                assert re.match(r"^[A-Z][A-Z0-9]  - ", line), line

    def test_le_type_ouvre_l_enregistrement(self):
        ris = export_ris(make_card(make_source()))
        assert ris.splitlines()[0].startswith("TY  - ")

    def test_fiche_sans_source_ne_casse_pas(self):
        assert export_ris(make_card()) == ""


class TestChamps:
    def test_un_auteur_par_ligne(self):
        # RIS n'accepte pas « AU  - Dupont, J.; Martin, A. » : chaque auteur
        # veut sa propre balise, sinon les gestionnaires n'en voient qu'un.
        ris = export_ris(make_card(make_source(authors="Adleman N., Menon V., Blasey C.")))
        au = [line for line in ris.splitlines() if line.startswith("AU  - ")]
        assert au == ["AU  - Adleman, N.", "AU  - Menon, V.", "AU  - Blasey, C."]

    def test_sans_auteur_aucune_ligne_au(self):
        assert "AU  - " not in export_ris(make_card(make_source(authors=None)))

    def test_annee_et_date_complete(self):
        ris = export_ris(make_card(make_source(published_at=datetime(2022, 3, 14))))
        assert "PY  - 2022" in ris
        assert "DA  - 2022/03/14" in ris

    def test_sans_date_aucune_annee_inventee(self):
        ris = export_ris(make_card(make_source(published_at=None)))
        assert "PY  - " not in ris
        assert "DA  - " not in ris

    def test_champs_bibliographiques(self):
        ris = export_ris(
            make_card(
                make_source(
                    journal="Front. Psychol.",
                    volume="13",
                    pages="1-12",
                    doi="10.1/abc",
                    url="https://x.org/a",
                )
            )
        )
        assert "JO  - Front. Psychol." in ris
        assert "VL  - 13" in ris
        assert "SP  - 1-12" in ris
        assert "DO  - 10.1/abc" in ris
        assert "UR  - https://x.org/a" in ris

    def test_un_champ_absent_ne_produit_pas_de_balise_vide(self):
        # « DO  - » sans valeur ferait croire a un DOI vide.
        t = tags(export_ris(make_card(make_source())))
        for absent in ("DO", "JO", "VL", "SP", "PB"):
            assert absent not in t

    def test_note_multiligne_reste_lisible(self):
        # Une ligne sans balise casse le parsing : chaque ligne de note doit
        # etre reprefixee par N1.
        ris = export_ris(make_card(make_source(annotation="Ligne un\nLigne deux")))
        assert "N1  - Ligne un" in ris
        assert "N1  - Ligne deux" in ris
        for line in ris.splitlines():
            assert not line.strip() or "  - " in line


class TestTypes:
    def test_vocabulaire_ferme(self):
        assert "TY  - JOUR" in export_ris(make_card(make_source(category="article-scientifique")))
        assert "TY  - BOOK" in export_ris(make_card(make_source(category="livre")))
        assert "TY  - NEWS" in export_ris(make_card(make_source(category="article-presse")))

    def test_categorie_inconnue_retombe_sur_elec(self):
        # Un type RIS invente serait rejete a l'import.
        assert "TY  - ELEC" in export_ris(make_card(make_source(category="quoi-donc")))


class TestPivotPartage:
    def test_ris_et_bibtex_decoupent_les_noms_pareil(self):
        # Les deux derivent du meme pivot CSL : ils ne peuvent pas diverger.
        card = make_card(make_source(authors="Dupont, Marie"))
        assert "AU  - Dupont, Marie" in export_ris(card)
        assert "author = {Dupont, Marie}" in export_bibtex(card)

    def test_bibtex_separe_les_auteurs_par_and(self):
        # « and » est le seul separateur que LaTeX comprend.
        bib = export_bibtex(make_card(make_source(authors="Adleman N., Menon V.")))
        assert "author = {Adleman, N. and Menon, V.}" in bib
