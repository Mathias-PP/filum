"""La fiche vitrine doit demontrer le produit, pas ses absences.

Constate en aout 2026 : les 18 sources de /@example/memoire-et-cerveau
n'avaient ni date, ni DOI, ni revue. Consequence en cascade -- tous les noeuds
du graphe affichaient « s. d. », le mode chronologie n'avait aucun sens, et
faute de DOI l'acces libre comme la retractation retombaient sur « non
verifiable » : 90 cellules d'absence sur 144 dans le tableau comparatif. Le
comportement etait correct, la donnee etait vide, et c'est la premiere page
que voit un visiteur venu du bouton « Voir un exemple ».

Ces tests verrouillent le contenu de la demo, pas le code qui la charge.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from app.models.source import Source, SourceStance
from app.models.source_excerpt import SourceExcerpt
from app.scripts.seed_demo import _demo_sources, _verdicts_par_extrait

SPEC = _demo_sources()
RELU_LE = datetime(2026, 8, 16, 12, 0, 0)


class TestDemontrabilite:
    def test_assez_de_sources_datees_pour_une_frise(self):
        """Une chronologie a besoin d'un etalement, pas d'une seule date."""
        dated = [s for s in SPEC if s.get("published_at")]
        assert len(dated) >= 8
        years = {s["published_at"].year for s in dated}
        assert max(years) - min(years) >= 50

    def test_assez_de_doi_pour_exercer_les_verdicts(self):
        """Sans DOI, ni l'acces libre ni la retractation n'ont de prise : la
        demo n'afficherait que « non verifiable »."""
        assert len([s for s in SPEC if s.get("doi")]) >= 5

    def test_les_trois_positions_declarables_sont_representees(self):
        """La colonne « position » du tableau comparatif serait sinon une
        colonne d'absences."""
        declared = {s["stance"] for s in SPEC if s.get("stance")}
        assert declared == {s.value for s in SourceStance}

    def test_des_sources_restent_sans_date(self):
        """Une demo entierement remplie mentirait dans l'autre sens : le
        produit doit montrer comment il traite ce qu'il ignore."""
        assert any(not s.get("published_at") for s in SPEC)


class TestVeracite:
    def test_les_doi_ont_la_forme_d_un_doi(self):
        for s in SPEC:
            doi = s.get("doi")
            if doi:
                assert re.fullmatch(r"10\.\d{4,9}/\S+", doi), doi

    def test_une_revue_n_est_annoncee_qu_avec_un_doi(self):
        """Une revue affichee sans identifiant qui la corrobore serait une
        affirmation invendable."""
        for s in SPEC:
            if s.get("journal"):
                assert s.get("doi"), s["title"]

    def test_aucune_url_vers_un_domaine_fantome(self):
        """`lea-marchand.filum.app` ne resout pas et porte l'ancienne marque :
        un lien mort sur la fiche vitrine coute la confiance qu'elle vend."""
        for s in SPEC:
            assert "filum.app" not in s["url"], s["url"]

    def test_les_dates_sont_des_dates(self):
        for s in SPEC:
            pub = s.get("published_at")
            if pub is not None:
                assert isinstance(pub, date), s["title"]
                assert 1800 <= pub.year <= 2100, pub

    def test_une_source_citee_mot_a_mot_est_une_source_cle(self):
        """Citer un passage, c'est declarer qu'on s'y appuie.

        La fiche affichait quatre sources porteuses d'extraits verbatim sans
        le badge « source cle », et deux sources clees dont on ne citait rien :
        le lecteur voyait la marque de l'appui a cote de ce qui ne l'appuie
        pas.
        """
        for s in SPEC:
            if s.get("excerpts"):
                assert s["is_pivot"], s["title"]


class TestVerdictsSurvivants:
    """Le seed efface et recree les sources a chaque demarrage du conteneur.

    Sans report, la vitrine repart a « jamais verifie » a chaque deploiement :
    la page qui vend la relecture des sources n'en montre alors aucune preuve.
    """

    def _source(self, url: str, extraits: list[tuple[str, str | None]]) -> Source:
        source = Source(url=url)
        source.excerpts = [
            SourceExcerpt(
                position=i,
                text=texte,
                verified_status=statut,
                verified_at=RELU_LE if statut else None,
                verified_text_source="fetched" if statut else None,
            )
            for i, (texte, statut) in enumerate(extraits)
        ]
        return source

    def test_un_verdict_rendu_est_retrouve_par_son_texte(self):
        sources = [self._source("https://a.example/x", [("un extrait", "found")])]
        verdicts = _verdicts_par_extrait(sources)
        assert verdicts[("https://a.example/x", "un extrait")].statut == "found"

    def test_un_extrait_jamais_relu_n_est_pas_reporte(self):
        sources = [self._source("https://a.example/x", [("un extrait", None)])]
        assert _verdicts_par_extrait(sources) == {}

    def test_le_verdict_est_lie_au_couple_source_texte(self):
        """Un texte reecrit doit etre relu : lui reporter l'ancien verdict
        affirmerait « retrouve dans la source » d'une phrase jamais cherchee."""
        sources = [
            self._source("https://a.example/x", [("ancien texte", "found")]),
            self._source("https://b.example/y", [("ancien texte", "missing")]),
        ]
        verdicts = _verdicts_par_extrait(sources)
        assert verdicts.get(("https://a.example/x", "texte reecrit")) is None
        assert verdicts[("https://b.example/y", "ancien texte")].statut == "missing"

    def test_la_date_et_la_provenance_voyagent_avec_le_verdict(self):
        """Un verdict seul se lit « Relu dans la source » sans date, et
        l'interface ne peut plus dire contre quoi la relecture a ete faite."""
        sources = [self._source("https://a.example/x", [("un extrait", "found")])]
        reporte = _verdicts_par_extrait(sources)[("https://a.example/x", "un extrait")]
        assert reporte.date == RELU_LE
        assert reporte.provenance == "fetched"


class TestChargeable:
    def test_chaque_entree_construit_une_source(self):
        """Un champ ajoute au spec mais pas au modele passerait sinon
        inapercu jusqu'au demarrage du conteneur."""
        for position, s in enumerate(SPEC):
            Source(
                position=position,
                url=s["url"],
                title=s["title"],
                authors=s["authors"],
                format=s["format"],
                category=s["category"],
                author_kind=s["author_kind"],
                annotation=s["annotation"],
                is_pivot=s["is_pivot"],
                doi=s.get("doi"),
                journal=s.get("journal"),
                published_at=s.get("published_at"),
                stance=s.get("stance"),
            )
