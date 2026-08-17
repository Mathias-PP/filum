"""Le garde-fou anti extrait hors-contexte.

Une phrase courte qui commence par un pronom ou un demonstratif sans
antecedent visible se lit, cite seule, comme un contresens. Le garde-fou
partage entre l'endpoint /excerpts/suggest et le tool MCP add_excerpt
refuse ces passages a moins qu'une mise en situation explicite ne nomme
le referent.

Ces tests figent la liste des marqueurs et le seuil, pour qu'un
elargissement futur (autres langues, cas subtils) se voie explicitement.
"""

from __future__ import annotations

import pytest

from app.services.excerpt_guards import (
    LONGUEUR_MIN_AUTONOME_MOTS,
    passage_a_besoin_de_contexte,
)


class TestPronomsFrancaisEnTete:
    @pytest.mark.parametrize(
        "extrait",
        [
            "Cela ameliore la memoire.",
            "C'est le point cle du dispositif.",
            "Ces travaux montrent que le sommeil consolide.",
            "Ceux qui l'ont teste rapportent des effets.",
            "Il reste a valider ce resultat.",
            "Elle propose une explication.",
            "Ils constatent une baisse.",
            "Ce phenomene se produit rarement.",
            "Cette hypothese est robuste.",
            "Cet effet disparait sous placebo.",
        ],
    )
    def test_marqueurs_referentiels_sont_detectes(self, extrait):
        assert passage_a_besoin_de_contexte(extrait) is True


class TestPronomsAnglaisEnTete:
    """Les modeles LLM produisent souvent en anglais quand la source est en
    anglais. La liste couvre les equivalents ordinaires pour ne pas laisser
    passer un « This study demonstrates that… » cite hors contexte."""

    @pytest.mark.parametrize(
        "extrait",
        [
            "This improves recall.",
            "That is the finding of the paper.",
            "These results are surprising.",
            "Those effects vanish with placebo.",
            "It suggests a mechanism.",
            "They show an increase.",
            "Such patterns emerge.",
            "This study demonstrates that…",
        ],
    )
    def test_marqueurs_anglais_referentiels_sont_detectes(self, extrait):
        assert passage_a_besoin_de_contexte(extrait) is True


class TestPassagesAutonomes:
    """A l'inverse : un passage qui pose lui-meme son sujet doit passer.
    Ces tests figent les faux positifs a eviter -- une regle trop stricte
    tuerait des extraits legitimes qui commencent par un article ordinaire."""

    @pytest.mark.parametrize(
        "extrait",
        [
            "La memoire se consolide pendant le sommeil profond.",
            "Les enfants de six ans montrent deja une inhibition mesurable.",
            "L'hippocampe joue un role decisif dans l'encodage.",
            "Selon les auteurs, la reconsolidation est reversible.",
            "Reconsolider un souvenir demande une reactivation.",
            "In this experiment, participants were shown three images.",
            "Memory consolidation requires slow-wave sleep.",
            "Neurons in the CA1 region fire during replay.",
        ],
    )
    def test_passages_qui_posent_leur_sujet_ne_declenchent_pas_le_garde_fou(self, extrait):
        # « La memoire », « Les enfants », « L'hippocampe » commencent par un
        # article mais nomment leur sujet dans la meme phrase : autonomes.
        assert passage_a_besoin_de_contexte(extrait) is False


class TestSeuil:
    def test_le_seuil_est_de_quinze_mots(self):
        """C'est le meme seuil que le prompt LLM demande d'atteindre. Le
        changer ici sans le changer la-bas produirait des extraits proposes
        par le LLM puis rejetes par le garde-fou, sans que l'user voie ni
        l'un ni l'autre."""
        assert LONGUEUR_MIN_AUTONOME_MOTS == 15

    def test_les_espaces_de_tete_ne_masquent_pas_le_marqueur(self):
        assert passage_a_besoin_de_contexte("   Cela ameliore la memoire.") is True

    def test_un_marqueur_au_milieu_ne_compte_pas(self):
        """La regle ne mord que sur le DEBUT du passage : c'est la que le
        pronom orphelin fait mal. Un pronom au milieu est generalement lie
        au premier bout de phrase, donc lisible."""
        assert (
            passage_a_besoin_de_contexte("La memoire se consolide, et cela dure des annees.")
            is False
        )
