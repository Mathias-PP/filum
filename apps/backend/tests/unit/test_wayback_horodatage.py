"""L'horodatage d'une archive dit quand la capture a ete faite.

Constate en production sur la fiche vitrine : chaque source portait
`archive_url = .../web/20240601000000/...` et `archive_timestamp` = l'instant
du dernier demarrage du conteneur. Le meme enregistrement affirmait donc deux
dates de capture differentes, dont l'une changeait a chaque deploiement.

Une archive a une date : celle que l'URL Wayback porte deja. Quand l'URL ne la
porte pas, l'absence vaut mieux qu'une date inventee.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.wayback import horodatage_wayback


class TestUrlWayback:
    def test_l_instantane_donne_sa_date(self):
        assert horodatage_wayback(
            "https://web.archive.org/web/20240601000000/https://example.org/a"
        ) == datetime(2024, 6, 1, 0, 0, 0)

    def test_l_heure_est_lue_aussi(self):
        assert horodatage_wayback(
            "https://web.archive.org/web/20190312143005/https://example.org/a"
        ) == datetime(2019, 3, 12, 14, 30, 5)

    @pytest.mark.parametrize("suffixe", ["id_", "im_", "if_"])
    def test_les_drapeaux_de_rendu_ne_genent_pas(self, suffixe):
        # `…/20240601000000id_/…` sert la capture brute : c'est la meme capture,
        # donc la meme date.
        url = f"https://web.archive.org/web/20240601000000{suffixe}/https://example.org/a"
        assert horodatage_wayback(url) == datetime(2024, 6, 1)

    def test_le_protocole_indiffere(self):
        assert horodatage_wayback(
            "http://web.archive.org/web/20240601000000/http://example.org/a"
        ) == datetime(2024, 6, 1)


class TestAbsenceDeDate:
    def test_un_horodatage_partiel_n_est_pas_complete(self):
        # « /web/2024/ » dit l'annee. En deduire le 1er janvier fabriquerait un
        # jour et une heure que personne n'a mesures.
        assert horodatage_wayback("https://web.archive.org/web/2024/https://example.org/a") is None

    def test_une_archive_ailleurs_ne_ment_pas_sur_sa_date(self):
        # archive.today ne met pas la date dans l'URL : on ne la connait pas.
        assert horodatage_wayback("https://archive.ph/abcde") is None

    def test_une_url_quelconque_ne_donne_rien(self):
        assert horodatage_wayback("https://example.org/web/20240601000000/x") is None

    def test_rien_a_lire(self):
        assert horodatage_wayback(None) is None
        assert horodatage_wayback("") is None

    def test_une_date_impossible_est_refusee(self):
        # 14 chiffres ne font pas une date : le 32 fevrier n'existe pas.
        assert (
            horodatage_wayback("https://web.archive.org/web/20243201000000/https://example.org/a")
            is None
        )
