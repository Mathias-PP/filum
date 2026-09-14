"""Un titre ou un auteur de source qui n'en est pas un ne peut pas etre inscrit.

Cas mesures le 2026-09-14 sur la base de production.
"""

from __future__ import annotations

import pytest

from app.core.champs_bibliographiques import auteurs_bibliographiques, titre_bibliographique
from app.models.source import Source

PMC = "https://pmc.ncbi.nlm.nih.gov/articles/PMC6419978/"
AMELI = "https://www.ameli.fr/assure/sante/themes/regles-douloureuses/douleurs-regles"


@pytest.mark.parametrize(
    "titre",
    [
        "Checking your browser - reCAPTCHA",
        "Just a moment...",
        "Attention Required! | Cloudflare",
        "reCAPTCHA",
        "403 Forbidden",
        "Page introuvable",
        "https://www.inserm.fr/dossier/endometriose/",
    ],
)
def test_un_titre_de_page_obstacle_ou_d_erreur_est_refuse(titre):
    assert titre_bibliographique(titre, PMC) is None


def test_un_segment_d_adresse_n_est_pas_un_titre():
    assert titre_bibliographique("regles-douloureuses", AMELI) is None
    # Sans l'adresse, un titre court a trait d'union reste possible.
    assert titre_bibliographique("covid-19", "https://exemple.test/dossier") == "covid-19"


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        (
            "Reversal of Synaptic Memory by Ca<sup>2+</sup>/Calmodulin-Dependent Protein Kinase II Inhibitor",
            "Reversal of Synaptic Memory by Ca2+/Calmodulin-Dependent Protein Kinase II Inhibitor",
        ),
        (
            "Posttetanic Potentiation at\n            <i>Aplysia</i>\n            Synapses",
            "Posttetanic Potentiation at Aplysia Synapses",
        ),
        ("Guerre &amp; paix : la r&eacute;ception russe", "Guerre & paix : la réception russe"),
        # Cas releves par la passe a blanc du 2026-09-14 sur la production.
        (
            "Long-Term Synaptic Tagging in Hippocampal CA1 Neurons in Slices<i>In Vitro</i>",
            "Long-Term Synaptic Tagging in Hippocampal CA1 Neurons in Slices In Vitro",
        ),
        (
            "PKMζ Maintains Late Long-Term Potentiation by\n  <i>N</i>\n  -Ethylmaleimide-Sensitive Factor",
            "PKMζ Maintains Late Long-Term Potentiation by N-Ethylmaleimide-Sensitive Factor",
        ),
        (
            "Involvement of Pre- and Postsynaptic Mechanisms",
            "Involvement of Pre- and Postsynaptic Mechanisms",
        ),
        ("in dendrites (n > 6,000)", "in dendrites (n > 6,000)"),
    ],
)
def test_les_balises_et_entites_sont_retirees(brut, attendu):
    assert titre_bibliographique(brut) == attendu


@pytest.mark.parametrize(
    "titre",
    [
        "reCAPTCHA: Human-Based Character Recognition via Web Security Measures",
        "Access denied: the history of censorship in Soviet libraries",
        "Le droit de grève dans la jurisprudence du Conseil constitutionnel",
    ],
)
def test_un_vrai_titre_passe_intact(titre):
    assert titre_bibliographique(titre, "https://exemple.test/article") == titre


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("https://www.facebook.com/inserm.fr", None),
        ("@inserm", None),
        ("Inserm; https://twitter.com/inserm", "Inserm"),
        ("Bao J., Kandel E., Hawkins R.", "Bao J., Kandel E., Hawkins R."),
        ("", None),
    ],
)
def test_une_adresse_de_profil_n_est_pas_un_auteur(brut, attendu):
    assert auteurs_bibliographiques(brut) == attendu


def test_le_modele_applique_la_regle_a_chaque_affectation():
    source = Source(
        url=PMC,
        title="Checking your browser - reCAPTCHA",
        authors="https://www.facebook.com/inserm.fr",
        format="texte",
        category="page-web",
        author_kind="institution-publique",
    )
    assert source.title is None
    assert source.authors is None

    source.title = "Recent advances in <i>understanding</i> adenomyosis"
    assert source.title == "Recent advances in understanding adenomyosis"


def test_changer_l_adresse_retire_un_titre_qui_n_en_etait_qu_un_segment():
    source = Source(
        url="https://exemple.test/a",
        title="regles-douloureuses",
        format="texte",
        category="page-web",
        author_kind="institution-publique",
    )
    assert source.title == "regles-douloureuses"
    source.url = AMELI
    assert source.title is None
