"""Semantic Scholar — parsing des references citees.

Le module `semantic_scholar` traduit les items S2 vers des `SemanticScholarRef`.
Deux categories de defauts a couvrir :

1. Les champs S2 qui « ressemblent a un titre » sans en etre (raw_text de
   citation brute, journal quand c'est le seul champ) : les prendre pour un
   titre affichait 187 references toutes intitulees du nom de leur revue.
2. Les caracteres qui cassent la serialisation JSON aval (surrogates
   orphelins, soft hyphens invisibles, tirets Unicode divers).

Les tests portent sur les fonctions pures (parsing, sanitize, format
authors) : pas d'appel reseau, pas de mock httpx.
"""

from __future__ import annotations

from app.extractors.semantic_scholar import (
    SemanticScholarRef,
    _extract_url_from_ext_ids,
    _format_authors,
    _parse_referenced_paper,
    _sanitize_text,
)


class TestExtractUrlFromExtIds:
    def test_doi_est_normalise_en_minuscules(self):
        doi, url = _extract_url_from_ext_ids({"DOI": "10.1038/NATURE12373"})
        assert doi == "10.1038/nature12373"
        assert url == "https://doi.org/10.1038/nature12373"

    def test_arxiv_est_rendu_url_sans_doi(self):
        doi, url = _extract_url_from_ext_ids({"ArXiv": "2103.15807"})
        assert doi is None
        assert url == "https://arxiv.org/abs/2103.15807"

    def test_pubmed_est_rendu_url_sans_doi(self):
        doi, url = _extract_url_from_ext_ids({"PubMed": "12345678"})
        assert doi is None
        assert url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    def test_doi_prime_arxiv(self):
        """Ordre de preference : DOI puis ArXiv puis PubMed."""
        doi, url = _extract_url_from_ext_ids({"DOI": "10.1000/x", "ArXiv": "2000.0001"})
        assert doi == "10.1000/x"
        assert "doi.org" in url

    def test_dict_vide_ou_none_rend_deux_nones(self):
        assert _extract_url_from_ext_ids(None) == (None, None)
        assert _extract_url_from_ext_ids({}) == (None, None)

    def test_ext_ids_sans_id_connu_rend_deux_nones(self):
        assert _extract_url_from_ext_ids({"SomethingElse": "x"}) == (None, None)


class TestSanitizeText:
    def test_supprime_les_surrogates_orphelins(self):
        """Les surrogates orphelins (\\ud800-\\udfff) apparaissent dans certains
        titres S2 issus de Wiley/PMC et cassent la serialisation JSON aval."""
        # Un demi-surrogate isole = invalide en UTF-8, remplace par tiret.
        assert _sanitize_text("Titre\ud800suite") == "Titre-suite"

    def test_normalise_les_tirets_unicode(self):
        """hyphen U+2010, non-breaking U+2011, figure U+2012, en-dash U+2013,
        em-dash U+2014 doivent tous devenir un simple '-' ASCII."""
        assert _sanitize_text("A‐B‑C‒D–E—F") == "A-B-C-D-E-F"

    def test_efface_les_soft_hyphens(self):
        """Soft hyphen U+00AD est invisible mais casse la dedup entre deux
        titres qui devraient etre identiques."""
        assert _sanitize_text("Micro­biote") == "Microbiote"

    def test_chaine_vide_apres_nettoyage_rend_none(self):
        assert _sanitize_text("   ") is None
        assert _sanitize_text("") is None

    def test_none_reste_none(self):
        assert _sanitize_text(None) is None

    def test_ne_touche_pas_un_titre_ordinaire(self):
        assert _sanitize_text("The hygiene hypothesis") == "The hygiene hypothesis"


class TestFormatAuthors:
    def test_concatene_famille_g_avec_virgule(self):
        raw = [{"name": "Kang W."}, {"name": "Hernandez S."}]
        assert _format_authors(raw) == "Kang W., Hernandez S."

    def test_cap_a_dix_auteurs(self):
        """Les papiers a 200 auteurs (physique haute energie) rendraient
        illisible l'affichage. On coupe raisonnablement."""
        raw = [{"name": f"Author{i}."} for i in range(50)]
        formatte = _format_authors(raw)
        assert formatte.count(",") == 9  # dix auteurs = neuf virgules

    def test_ignore_les_auteurs_sans_nom(self):
        raw = [{"name": "Alpha"}, {"name": None}, {"name": "Bravo"}]
        assert _format_authors(raw) == "Alpha, Bravo"

    def test_liste_vide_ou_none_rend_none(self):
        assert _format_authors(None) is None
        assert _format_authors([]) is None


class TestParseReferencedPaper:
    def _item(self, **paper_overrides) -> dict:
        paper = {
            "title": "Sample paper",
            "authors": [{"name": "Doe J."}],
            "year": 2024,
            "externalIds": {"DOI": "10.1000/sample"},
            **paper_overrides,
        }
        return {"citedPaper": paper}

    def test_item_nominal_rend_ref_complete(self):
        ref = _parse_referenced_paper(self._item())
        assert isinstance(ref, SemanticScholarRef)
        assert ref.title == "Sample paper"
        assert ref.authors == "Doe J."
        assert ref.year == 2024
        assert ref.doi == "10.1000/sample"
        assert ref.url == "https://doi.org/10.1000/sample"

    def test_item_sans_citedpaper_rend_none(self):
        assert _parse_referenced_paper({}) is None
        assert _parse_referenced_paper({"citedPaper": None}) is None
        assert _parse_referenced_paper("pas un dict") is None

    def test_item_sans_url_exploitable_garde_les_metadata(self):
        """Une ref sans DOI/ArXiv/PubMed reste utile pour ses metadonnees ;
        c'est le pipeline en aval qui decide de la skipper."""
        ref = _parse_referenced_paper(self._item(externalIds=None))
        assert ref is not None
        assert ref.url is None
        assert ref.title == "Sample paper"
        assert ref.doi is None

    def test_titre_avec_caracteres_sales_est_sanitize(self):
        """Un titre S2 avec des caracteres Unicode invalides ne doit pas
        empoisonner la fiche generee en aval."""
        ref = _parse_referenced_paper(self._item(title="Micro­biote\ud800end"))
        assert ref.title == "Microbiote-end"
