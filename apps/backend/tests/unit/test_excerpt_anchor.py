"""Un extrait cite doit rester retrouvable dans une source qui bouge.

Aujourd'hui un extrait ne porte que son texte : le retrouver, c'est le chercher
au mot pres. Une page qui corrige une coquille, insere une incise ou change de
gabarit fait echouer cette recherche — et l'extrait, faute d'etre retrouve, se
lit alors comme une citation inventee. C'est exactement le mode d'echec que
Philum existe pour eliminer.

Hypothes.is a resolu ce probleme et l'a documente : on stocke *plusieurs*
selecteurs pour la meme cible — le texte exact, son voisinage immediat, et une
position approximative — puis on les essaie du moins cher au plus robuste.

Ces tests tiennent la promesse correspondante : ce qui a ete cite reste
retrouve, et ce qui ne l'a pas ete n'est jamais retrouve par complaisance.
"""

from __future__ import annotations

import re

from app.services.excerpt_anchor import ancrer, selecteurs_pour

PAGE = (
    "La memoire de travail retient une information brievement. "
    "Elle ne dure que quelques secondes chez l'adulte. "
    "Baddeley en a propose un modele en 1974. "
    "Ce modele distingue plusieurs sous-systemes."
)
CITATION = "Elle ne dure que quelques secondes chez l'adulte."


def _selecteurs(page: str = PAGE, quote: str = CITATION):
    debut = page.index(quote)
    return selecteurs_pour(page, debut, debut + len(quote))


class TestSelecteurs:
    def test_capture_le_texte_et_son_voisinage(self):
        sel = _selecteurs()
        assert sel.quote == CITATION
        assert sel.prefix.endswith("brievement. ")
        assert sel.suffix.lstrip().startswith("Baddeley")
        assert sel.offset == PAGE.index(CITATION)

    def test_le_voisinage_s_arrete_aux_bords_du_texte(self):
        # Une citation en tete de page n'a pas de prefixe : c'est un fait, pas
        # une erreur, et le selecteur doit pouvoir le dire sans lever.
        sel = selecteurs_pour(PAGE, 0, 20)
        assert sel.prefix == ""
        assert sel.quote == PAGE[:20]


class TestAncrage:
    def test_retrouve_le_passage_inchange(self):
        a = ancrer(PAGE, _selecteurs())
        assert a is not None
        assert a.exact is True
        assert PAGE[a.start : a.end] == CITATION

    def test_retrouve_malgre_un_deplacement_du_texte(self):
        # Un paragraphe ajoute en tete decale tous les offsets. La position
        # stockee devient fausse ; le texte, lui, est toujours la.
        page = "Un chapeau ajoute par la redaction. " + PAGE
        a = ancrer(page, _selecteurs())
        assert a is not None
        assert a.exact is True
        assert page[a.start : a.end] == CITATION

    def test_retrouve_malgre_une_reprise_de_mise_en_forme(self):
        # Retours a la ligne et espaces multiples sont du gabarit, pas du texte.
        page = PAGE.replace(" ", "\n  ")
        a = ancrer(page, _selecteurs())
        assert a is not None
        assert a.exact is True
        assert " ".join(page[a.start : a.end].split()) == CITATION

    def test_retrouve_malgre_une_coquille_corrigee(self):
        # Le cas qui motive tout : la page a change, pas la citation. Un mot
        # corrige ne doit pas transformer un extrait honnete en citation
        # introuvable — mais le resultat n'est plus exact, et le dit.
        page = PAGE.replace("quelques secondes", "quelques secondes seulement")
        a = ancrer(page, _selecteurs())
        assert a is not None
        assert a.exact is False
        assert "quelques secondes seulement" in page[a.start : a.end]

    def test_choisit_l_occurrence_dont_le_voisinage_correspond(self):
        # Deux fois la meme phrase : sans le voisinage, on ancrerait sur la
        # premiere venue et le « voir en contexte » montrerait le mauvais
        # endroit.
        repetee = "Le resultat est net."
        page = f"Premier passage. {repetee} Suite du premier. Second passage. {repetee} Fin."
        second = page.rindex(repetee)
        sel = selecteurs_pour(page, second, second + len(repetee))
        a = ancrer(page, sel)
        assert a is not None
        assert a.start == second

    def test_l_offset_departage_deux_occurrences_indiscernables(self):
        # Meme phrase, meme voisinage des deux cotes : le contexte ne dit plus
        # rien. La position d'origine est le seul depart qui reste — et rendre
        # la premiere venue montrerait le mauvais passage une fois sur deux.
        # Motif periodique — une liste, un tableau de resultats repetitif : le
        # voisinage de la 2e et de la 3e occurrence est le meme caractere pour
        # caractere.
        phrase = "Le resultat est net."
        page = f"Item. {phrase} Suite du bloc courant. " * 4
        cible = [m.start() for m in re.finditer(re.escape(phrase), page)][2]
        sel = selecteurs_pour(page, cible, cible + len(phrase))
        voisins = [m.start() for m in re.finditer(re.escape(phrase), page)]
        assert page[voisins[1] - 48 : voisins[1]] == page[cible - 48 : cible]
        a = ancrer(page, sel)
        assert a is not None
        assert a.start == cible

    def test_ne_retrouve_rien_dans_un_texte_etranger(self):
        # Le point dur : un ancrage complaisant est pire que pas d'ancrage. Il
        # affirmerait que la source contient un passage qu'elle ne contient pas.
        autre = (
            "Les abeilles butinent selon un trajet optimise. "
            "La colonie ajuste sa strategie de recolte au fil des saisons."
        )
        assert ancrer(autre, _selecteurs()) is None

    def test_ne_retrouve_rien_dans_un_texte_vide(self):
        assert ancrer("", _selecteurs()) is None
