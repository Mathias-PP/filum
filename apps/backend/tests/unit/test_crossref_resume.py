"""Un resume JATS rendu comparable au texte d'une page.

Ce nettoyage est la raison d'etre du module : `_parse_crossref_work` remplace
les balises par du vide, ce qui suffit a afficher un resume mais soude les mots
de part et d'autre d'une fin de paragraphe. Un corpus d'ancrage ne le supporte
pas : l'extrait cherche « du glucose. The Warburg » et la page porterait
« du glucose.The Warburg », donc le passage serait declare absent d'une source
qui le contient.
"""

from __future__ import annotations

from app.extractors.crossref_resume import texte_du_resume


class TestTexteDuResume:
    def test_un_resume_absent_rend_la_chaine_vide(self):
        assert texte_du_resume(None) == ""
        assert texte_du_resume("") == ""

    def test_les_balises_deviennent_une_espace_et_non_du_vide(self):
        """Le bug que ce module existe pour eviter."""
        brut = "<jats:p>du glucose.</jats:p><jats:p>The Warburg effect</jats:p>"
        assert texte_du_resume(brut) == "du glucose. The Warburg effect"

    def test_les_espaces_du_jats_sont_reduits(self):
        brut = "<jats:title>Abstract</jats:title>\n      <jats:p>Contrary   to\n Warburg</jats:p>"
        assert texte_du_resume(brut) == "Abstract Contrary to Warburg"

    def test_les_entites_sont_decodees(self):
        assert texte_du_resume("<jats:p>Warburg &amp; Krebs</jats:p>") == "Warburg & Krebs"

    def test_une_entite_echappee_n_est_pas_prise_pour_une_balise(self):
        """Le decodage vient apres le retrait des balises, jamais avant.

        Dans l'autre ordre, un `&lt;p&gt;` ecrit litteralement dans le resume
        deviendrait une balise et serait efface alors qu'il fait partie du texte.
        """
        assert texte_du_resume("<jats:p>la balise &lt;p&gt; ouvre</jats:p>") == (
            "la balise <p> ouvre"
        )
