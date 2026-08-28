"""La lecture par l'archive du web, la seule route qui ignore le domaine."""

from __future__ import annotations

import httpx
import pytest

from app.extractors import web_archive
from app.extractors.web_archive import derniere_capture, texte_archive, texte_de_la_capture


def _transport(gestionnaire):
    return httpx.MockTransport(gestionnaire)


@pytest.fixture
def sans_resolution(monkeypatch):
    """La resolution de redirections rend l'URL telle quelle."""

    async def tel_quel(url, _timeout=15.0):
        return url

    monkeypatch.setattr(web_archive, "resoudre_redirections", tel_quel)


def _client_simule(monkeypatch, gestionnaire):
    """Branche tout ``httpx.AsyncClient`` du module sur un transport simule."""
    vrai = httpx.AsyncClient

    def fabrique(*args, **kwargs):
        kwargs["transport"] = _transport(gestionnaire)
        kwargs.pop("event_hooks", None)
        return vrai(*args, **kwargs)

    monkeypatch.setattr(web_archive.httpx, "AsyncClient", fabrique)


class TestDerniereCapture:
    @pytest.mark.asyncio
    async def test_la_ligne_utile_est_la_seconde(self, monkeypatch):
        # CDX rend une matrice dont la premiere ligne est l'en-tete. La lire
        # comme une donnee ferait demander la capture « timestamp ».
        def gestionnaire(_requete):
            return httpx.Response(
                200,
                json=[
                    ["timestamp", "original"],
                    ["20250816002252", "https://presse.example/enquete"],
                ],
            )

        _client_simule(monkeypatch, gestionnaire)
        adresse, horodatage = await derniere_capture("https://presse.example/enquete")
        assert horodatage == "20250816002252"
        # `id_` : sans ce drapeau, le texte melange l'article et la banniere
        # de rejeu injectee par archive.org.
        assert adresse == (
            "https://web.archive.org/web/20250816002252id_/https://presse.example/enquete"
        )

    @pytest.mark.asyncio
    async def test_un_index_vide_ne_donne_rien(self, monkeypatch):
        _client_simule(monkeypatch, lambda _r: httpx.Response(200, json=[]))
        assert await derniere_capture("https://presse.example/enquete") is None

    @pytest.mark.asyncio
    async def test_un_html_d_erreur_servi_en_200_ne_conclut_pas(self, monkeypatch):
        # Une absence ne s'affirme que sur une reponse saine : conclure ici
        # dirait « jamais archivee » d'une page qu'on n'a pas su interroger.
        _client_simule(monkeypatch, lambda _r: httpx.Response(200, text="<html>oups</html>"))
        assert await derniere_capture("https://presse.example/enquete") is None

    @pytest.mark.asyncio
    async def test_un_index_injoignable_ne_leve_pas(self, monkeypatch):
        def gestionnaire(_requete):
            raise httpx.ConnectError("archive.org injoignable")

        _client_simule(monkeypatch, gestionnaire)
        assert await derniere_capture("https://presse.example/enquete") is None

    @pytest.mark.asyncio
    async def test_le_second_canal_repond_quand_le_premier_se_tait(self, monkeypatch):
        # Mesure du 2026-08-28 : CDX rendait un ReadTimeout a une lecture sur
        # trois d'une page parfaitement archivee. Un seul canal ferait donc
        # echouer une lecture sur trois pour une raison sans rapport avec la
        # source.
        def gestionnaire(requete):
            if "cdx" in requete.url.path:
                raise httpx.ReadTimeout("")
            return httpx.Response(
                200,
                json={
                    "archived_snapshots": {
                        "closest": {
                            "url": "http://web.archive.org/web/20250816002252/https://x.example/a",
                            "timestamp": "20250816002252",
                        }
                    }
                },
            )

        _client_simule(monkeypatch, gestionnaire)
        trouve = await derniere_capture("https://x.example/a")
        assert trouve == (
            "https://web.archive.org/web/20250816002252id_/https://x.example/a",
            "20250816002252",
        )


class TestTexteDeLaCapture:
    def test_le_texte_est_aplati(self):
        html = (
            "<html><title>Enquete</title><body>"
            "<p>Le premier paragraphe.</p><p>Le second.</p>"
            "<p>" + "du remplissage " * 20 + "</p>"
            "</body></html>"
        )
        texte = texte_de_la_capture(html)
        assert texte is not None
        assert "Le premier paragraphe. Le second." in texte

    def test_une_capture_du_defi_anti_robot_ne_passe_pas(self):
        # L'archive a parfois capture l'obstacle plutot que la page. Rendre
        # « verification de votre navigateur » comme corps d'article ferait
        # conclure au modele que l'article ne dit rien.
        html = (
            "<html><title>Just a moment...</title><body>"
            "Checking your browser before accessing. Enable JavaScript and cookies to continue. "
            + "attendez " * 100
            + "</body></html>"
        )
        assert texte_de_la_capture(html) is None

    def test_une_capture_trop_courte_ne_passe_pas(self):
        # Une capture de redirection repond 200 avec trois mots. La rendre
        # ferait chercher un extrait dans un texte qui n'en contient aucun,
        # exactement la situation ou le modele en invente un.
        assert texte_de_la_capture("<html><body>Redirecting...</body></html>") is None


class TestTexteArchive:
    @pytest.mark.asyncio
    async def test_une_url_vide_n_appelle_pas_le_reseau(self):
        assert await texte_archive(None) is None
        assert await texte_archive("   ") is None

    @pytest.mark.asyncio
    async def test_la_capture_est_lue(self, monkeypatch, sans_resolution):
        corps = "<html><title>Enquete</title><body>" + "le texte " * 100 + "</body></html>"

        def gestionnaire(requete):
            if "cdx" in requete.url.path:
                return httpx.Response(
                    200,
                    json=[
                        ["timestamp", "original"],
                        ["20250816002252", str(requete.url.params["url"])],
                    ],
                )
            return httpx.Response(200, text=corps, headers={"content-type": "text/html"})

        _client_simule(monkeypatch, gestionnaire)
        texte = await texte_archive("https://presse.example/enquete")
        assert texte is not None
        assert "le texte" in texte

    @pytest.mark.asyncio
    async def test_l_url_cherchee_est_la_resolue(self, monkeypatch):
        # L'archive d'un resolveur n'a que des captures de redirection :
        # `doi.org/10.2174/…` n'en a aucune en 200, sa cible eurekaselect si.
        cherchees: list[str] = []

        async def resoudre(_url, _timeout=15.0):
            return "https://revue.example/article/79409"

        monkeypatch.setattr(web_archive, "resoudre_redirections", resoudre)

        def gestionnaire(requete):
            cherchees.append(str(requete.url.params["url"]))
            return httpx.Response(200, json=[])

        _client_simule(monkeypatch, gestionnaire)
        assert await texte_archive("https://doi.org/10.2174/1871520616666161031143301") is None
        assert set(cherchees) == {"https://revue.example/article/79409"}

    @pytest.mark.asyncio
    async def test_les_parametres_de_suivi_sont_retires(self, monkeypatch, sans_resolution):
        # CDX cherche l'URL exacte : `…/article?utm_source=x` et `…/article`
        # sont deux cles distinctes, et seule la seconde a une capture.
        cherchees: list[str] = []

        def gestionnaire(requete):
            cherchees.append(str(requete.url.params["url"]))
            return httpx.Response(200, json=[])

        _client_simule(monkeypatch, gestionnaire)
        await texte_archive("https://presse.example/enquete?utm_source=x")
        assert set(cherchees) == {"https://presse.example/enquete"}

    @pytest.mark.asyncio
    async def test_une_capture_non_html_est_ecartee(self, monkeypatch, sans_resolution):
        def gestionnaire(requete):
            if "cdx" in requete.url.path:
                return httpx.Response(
                    200, json=[["timestamp", "original"], ["20250816002252", "https://x.example/a"]]
                )
            return httpx.Response(200, text="%PDF-1.4", headers={"content-type": "application/pdf"})

        _client_simule(monkeypatch, gestionnaire)
        assert await texte_archive("https://x.example/a") is None
