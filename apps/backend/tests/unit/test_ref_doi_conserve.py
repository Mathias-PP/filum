"""Une reference deposee avec son DOI ne doit pas arriver sans.

Mesure du 2026-08-16 sur la fiche publiee « Real-world data and clinical
experience from over 100,000 multi-cancer early detection tests » : ses 50
references viennent de l'oracle Crossref, ou chacune porte son DOI et sa
revue. En base, les 50 sources ont `doi = null` et `journal = null`.

Deux verifications de la fiche en dependent, et affichent donc « Non
verifiable » sur toute fiche scientifique :

- la retractation, qui interroge Crossref par DOI : sans DOI, Philum ne peut
  pas dire qu'un article a ete retire de la litterature ;
- l'acces libre, qui interroge Unpaywall par DOI.

Le DOI etait porte jusqu'a `_s2_ref_to_imported_ref`, qui recopiait titre,
auteurs, annee et texte brut, mais laissait tomber `doi` et `journal`.
"""

from __future__ import annotations

from app.api.v1.endpoints.imports import _merge_s2_refs, _s2_ref_to_imported_ref, _to_draft
from app.extractors.semantic_scholar import SemanticScholarRef
from app.services.import_parsers import ImportedRef, ParseResult


def test_le_doi_et_la_revue_survivent_a_la_conversion():
    s2 = SemanticScholarRef(
        title="Multi-cancer early detection test in symptomatic patients",
        authors="Nicholson B., Oke J.",
        year=2023,
        doi="10.1016/s1470-2045(23)00277-2",
        url="https://doi.org/10.1016/s1470-2045(23)00277-2",
        journal="The Lancet Oncology",
    )

    ref = _s2_ref_to_imported_ref(s2)

    assert ref is not None
    assert ref.doi == "10.1016/s1470-2045(23)00277-2"
    assert ref.journal == "The Lancet Oncology"


def test_le_doi_arrive_jusqu_au_brouillon_servi_au_formulaire():
    #: C'est ce brouillon que le formulaire renvoie a la creation de source.
    #: Le perdre ici le perd en base, definitivement.
    s2 = SemanticScholarRef(
        title="Cancer statistics, 2024",
        doi="10.3322/caac.21820",
        url="https://doi.org/10.3322/caac.21820",
        journal="CA: A Cancer Journal for Clinicians",
    )

    ref = _s2_ref_to_imported_ref(s2)
    assert ref is not None
    draft = _to_draft(ref)

    assert draft.doi == "10.3322/caac.21820"
    assert draft.journal == "CA: A Cancer Journal for Clinicians"


def test_une_reference_sans_lien_garde_sa_revue():
    #: Un livre ou un chapitre sans DOI est conserve pour edition manuelle.
    #: Sa revue reste la seule metadonnee bibliographique qu'on ait.
    s2 = SemanticScholarRef(title="State of Lung Cancer 2024", journal="American Lung Association")

    ref = _s2_ref_to_imported_ref(s2)

    assert ref is not None
    assert ref.url == ""
    assert ref.journal == "American Lung Association"


def test_une_reference_sans_titre_ni_lien_reste_ecartee():
    assert _s2_ref_to_imported_ref(SemanticScholarRef()) is None


def test_une_ref_scrapee_sans_doi_recoit_celui_de_l_editeur():
    #: Le scraping HTML rend un lien et un titre, jamais un DOI. Quand l'oracle
    #: decrit la meme reference, c'est la seule occasion de le recuperer.
    base = ParseResult(
        refs=[
            ImportedRef(
                url="https://doi.org/10.3322/caac.21820",
                title="Cancer statistics, 2024",
                category="article-scientifique",
            )
        ]
    )

    fusion = _merge_s2_refs(
        base,
        [
            SemanticScholarRef(
                title="Cancer statistics, 2024",
                doi="10.3322/caac.21820",
                url="https://doi.org/10.3322/caac.21820",
                journal="CA: A Cancer Journal for Clinicians",
            )
        ],
    )

    assert len(fusion.refs) == 1
    assert fusion.refs[0].doi == "10.3322/caac.21820"
    assert fusion.refs[0].journal == "CA: A Cancer Journal for Clinicians"
