"""Le parametre de suivi d'un redirecteur cache la capture qui existe.

Mesure du 2026-08-04, confirmee le 2026-08-07 : `linkinghub` (redirecteur
Elsevier) ajoute `?via=ihub` a ses adresses. CDX cherche l'URL **exacte** :
la capture de `…/pii/S0896627301005839` existe depuis 2019, celle de la meme
adresse suffixee du parametre n'existe pas. La source restait donc affichee
« non archivee » alors que l'archive etait la.

Retirer la requete a l'aveugle serait pire : `article.aspx?doi=10.1/x`
deviendrait `article.aspx`, une page generique, et on archiverait la mauvaise
ressource. D'ou une liste **explicite** de parametres connus pour ne jamais
designer la ressource -- pas une heuristique.
"""

from __future__ import annotations

from app.services.wayback import strip_tracking_params


class TestParametresDeSuivi:
    def test_via_du_redirecteur_elsevier_est_retire(self):
        assert (
            strip_tracking_params(
                "https://linkinghub.elsevier.com/retrieve/pii/S0896627301005839?via=ihub"
            )
            == "https://linkinghub.elsevier.com/retrieve/pii/S0896627301005839"
        )

    def test_utm_est_retire(self):
        assert (
            strip_tracking_params("https://exemple.fr/a?utm_source=x&utm_medium=y")
            == "https://exemple.fr/a"
        )

    def test_un_identifiant_dans_la_requete_est_conserve(self):
        """Le cas qui interdit de vider la requete a l'aveugle : sans `doi`,
        l'adresse designe une page generique, et on archiverait la mauvaise
        ressource."""
        url = "https://revue.fr/article.aspx?doi=10.1000/xyz"
        assert strip_tracking_params(url) == url

    def test_les_parametres_utiles_survivent_au_menage(self):
        assert (
            strip_tracking_params("https://revue.fr/a?doi=10.1000/xyz&utm_source=newsletter")
            == "https://revue.fr/a?doi=10.1000/xyz"
        )

    def test_une_url_sans_requete_est_rendue_telle_quelle(self):
        url = "https://exemple.fr/page"
        assert strip_tracking_params(url) == url

    def test_l_ordre_des_parametres_utiles_est_preserve(self):
        """Reordonner changerait l'URL, donc la cle CDX : le menage ne doit
        rien deplacer."""
        url = "https://exemple.fr/a?b=2&a=1"
        assert strip_tracking_params(url) == url
