"""L'URL ne peut pas rester enfouie dans le titre.

Mesure sur la fiche vitrine `inhibitory-control-development` : la source de
l'American Lung Association s'affiche titre « State of Lung Cancer 2024
Report. https://www.lung.org/... (2024). », `url` vide, bouton « Version
live » qui ne mene nulle part. La citation vient d'un parseur libre qui
recopie l'entree telle qu'ecrite ; sans promotion, le champ dedie reste
vide et le lien affiche est purement decoratif.
"""

from __future__ import annotations

from app.services.import_parsers import (
    ImportedRef,
    parse_freetext_citations,
    promouvoir_lien_du_titre,
)


class TestPromotionURL:
    def test_l_url_dans_le_titre_devient_l_url_de_la_source(self):
        ref = ImportedRef(
            url="",
            title=(
                "State of Lung Cancer 2024 Report. "
                "https://www.lung.org/getmedia/12020193/SOLC-2024.pdf"
            ),
        )
        promouvoir_lien_du_titre(ref)
        assert ref.url == "https://www.lung.org/getmedia/12020193/SOLC-2024.pdf"
        assert ref.title == "State of Lung Cancer 2024 Report."

    def test_l_url_deja_presente_n_est_pas_ecrasee(self):
        """Le titre reste inchange si l'URL est deja portee : on ne promeut
        que ce qui manque, sinon on effacerait un lien deja pose a la main."""
        ref = ImportedRef(
            url="https://autre.example/vrai-lien",
            title="Titre avec https://parasite.example/autre",
        )
        promouvoir_lien_du_titre(ref)
        assert ref.url == "https://autre.example/vrai-lien"
        assert ref.title == "Titre avec https://parasite.example/autre"

    def test_le_doi_dans_le_titre_devient_le_doi_de_la_source(self):
        ref = ImportedRef(
            url="",
            title="Article important. 10.1038/nature11028",
        )
        promouvoir_lien_du_titre(ref)
        assert ref.doi == "10.1038/nature11028"
        assert ref.url == "https://doi.org/10.1038/nature11028"
        assert ref.title == "Article important."

    def test_le_doi_deja_present_n_est_pas_ecrase(self):
        ref = ImportedRef(
            url="https://x.example",
            doi="10.1234/vrai",
            title="Titre avec 10.9999/autre",
        )
        promouvoir_lien_du_titre(ref)
        assert ref.doi == "10.1234/vrai"

    def test_un_titre_sans_url_ni_doi_n_est_pas_touche(self):
        ref = ImportedRef(url="", title="Simple titre sans lien")
        promouvoir_lien_du_titre(ref)
        assert ref.url == ""
        assert ref.title == "Simple titre sans lien"
        assert ref.doi is None

    def test_le_titre_ne_devient_pas_vide_si_il_n_est_qu_une_url(self):
        """Si le titre n'etait qu'une URL, on la promeut mais on ne la
        supprime pas du titre : mieux vaut un titre = URL qu'un titre vide."""
        ref = ImportedRef(url="", title="https://example.org/document.pdf")
        promouvoir_lien_du_titre(ref)
        assert ref.url == "https://example.org/document.pdf"
        assert ref.title == "https://example.org/document.pdf"

    def test_la_ponctuation_orpheline_est_nettoyee(self):
        """Un « . » ou un « , » qui precedait l'URL ne doit pas rester en fin."""
        ref = ImportedRef(
            url="",
            title="Titre du rapport. https://example.org/doc.pdf (2024)",
        )
        promouvoir_lien_du_titre(ref)
        assert ref.url == "https://example.org/doc.pdf"
        assert ref.title == "Titre du rapport. (2024)"


class TestBoutEnBout:
    def test_le_cas_vitrine_ne_produit_plus_de_lien_mort(self):
        """La citation qui a revele le defaut, passee par le parseur libre."""
        citation = (
            "American Lung Association. State of Lung Cancer 2024 Report. "
            "https://www.lung.org/getmedia/12020193/SOLC-2024.pdf (2024)."
        )
        result = parse_freetext_citations(citation)
        assert len(result.refs) == 1
        ref = result.refs[0]
        assert ref.url == "https://www.lung.org/getmedia/12020193/SOLC-2024.pdf"
        assert "https://" not in (ref.title or "")
        assert "State of Lung Cancer" in (ref.title or "")
