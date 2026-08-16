"""Le texte plein d'un article PMC doit venir de l'API, pas du scraping.

Mesure du 2026-08-16 sur la fiche 1 : huit extraits restent « illisible »
alors que les articles cites sont en acces libre. La page HTML de PubMed et
de PMC repond un interstitiel reCAPTCHA aux IP de datacenter, et la relecture
conclut que la source est illisible, ce qui accuse l'auteur·ice a la place du
site.

NCBI publie pourtant le texte plein de son sous-ensemble Open Access en JSON
structure, sans cle ni captcha : pmcoa.cgi rend 167 ko de passages pour
PMC7723645 la ou le scraping rend zero caractere.

Ce module ne fait pas de reseau ici : on teste la reconnaissance des URLs et
le decoupage de la reponse.
"""

from __future__ import annotations

import json

from app.extractors.pmc_oracle import (
    est_url_ncbi,
    identifiant_depuis_url,
    texte_du_resume,
    texte_des_passages,
)


def test_une_url_pmc_est_reconnue():
    assert est_url_ncbi("https://pmc.ncbi.nlm.nih.gov/articles/PMC7723645/") is True
    assert est_url_ncbi("https://pubmed.ncbi.nlm.nih.gov/33313194/") is True


def test_une_url_ordinaire_ne_l_est_pas():
    assert (
        est_url_ncbi("https://www.frontiersin.org/articles/10.3389/fpsyg.2022.651547/full") is False
    )
    assert est_url_ncbi("pas une url") is False


def test_l_identifiant_se_lit_dans_l_url():
    #: L'API accepte indifferemment un PMCID et un PMID : aucune conversion
    #: prealable n'est necessaire.
    assert (
        identifiant_depuis_url("https://pmc.ncbi.nlm.nih.gov/articles/PMC7723645/") == "PMC7723645"
    )
    assert identifiant_depuis_url("https://pubmed.ncbi.nlm.nih.gov/33313194/") == "33313194"
    assert identifiant_depuis_url("https://www.nature.com/articles/s41586") is None


def test_les_passages_se_recollent_en_un_texte():
    reponse = json.dumps(
        [
            {
                "documents": [
                    {
                        "id": "PMC7723645",
                        "passages": [
                            {"infons": {"section_type": "TITLE"}, "text": "Chest CT imaging"},
                            {"infons": {"section_type": "ABSTRACT"}, "text": "Coronavirus disease"},
                        ],
                    }
                ]
            }
        ]
    )
    texte = texte_des_passages(reponse)
    assert texte is not None
    assert "Chest CT imaging" in texte
    assert "Coronavirus disease" in texte


def test_la_bibliographie_est_ecartee():
    #: Un extrait cite le corps d'un article, jamais une ligne de sa
    #: bibliographie. Garder les references ferait passer pour « retrouve »
    #: un extrait qui n'est que le titre d'un ouvrage cite.
    reponse = json.dumps(
        [
            {
                "documents": [
                    {
                        "passages": [
                            {"infons": {"section_type": "INTRO"}, "text": "Le corps du texte."},
                            {
                                "infons": {"section_type": "REF"},
                                "text": "Diamond A. Executive functions.",
                            },
                        ]
                    }
                ]
            }
        ]
    )
    texte = texte_des_passages(reponse)
    assert texte == "Le corps du texte."


def test_un_article_hors_acces_libre_ne_rend_rien():
    #: NCBI repond 200 avec un corps d'erreur en texte brut, pas en JSON. Le
    #: prendre pour du texte plein ferait declarer « introuvables » tous les
    #: extraits d'un article parfaitement valide.
    assert texte_des_passages("[Error] : No result can be found. <BR><HR>") is None


def test_une_reponse_vide_ne_rend_rien():
    assert texte_des_passages("[]") is None
    assert texte_des_passages('[{"documents": []}]') is None


def test_le_resume_est_du_texte_lisible():
    #: Cinq des huit extraits illisibles portent sur des articles absents du
    #: sous-ensemble Open Access. NCBI en publie le resume par efetch, sans
    #: captcha, et c'est la que ces extraits ont ete lus.
    corps = (
        "1. Lancet Oncol. 2023 Jul;24(7):733-743. doi: 10.1016/S1470-2045(23)00277-2.\n\n"
        "Multi-cancer early detection test in symptomatic patients referred for cancer\n"
        "investigation in England and Wales (SYMPLIFY).\n\n"
        "Nicholson BD, Oke J, Virdee PS.\n\n"
        "BACKGROUND: Tests are needed to help triage patients. " + "x" * 300
    )
    assert texte_du_resume(corps) == corps


def test_un_corps_trop_court_n_est_pas_un_resume():
    #: efetch rend une page d'erreur courte pour un identifiant inconnu. La
    #: prendre pour un resume ferait declarer l'extrait absent d'un texte qui
    #: n'est pas celui de la source.
    assert texte_du_resume("Error occurred: cannot get document summary") is None
    assert texte_du_resume("") is None
