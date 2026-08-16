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

from app.extractors.pmc_oracle import est_url_ncbi, identifiant_depuis_url, texte_des_passages


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
