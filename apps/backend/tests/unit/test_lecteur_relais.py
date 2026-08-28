"""Le relais de lecture, sans reseau.

Ce qui est verifie ici n'est pas que le relais lit bien une page (c'est le
travail du service tiers, mesure en production), mais qu'un relais defaillant ne
fait jamais echouer l'appelant et ne lui rend jamais autre chose qu'un article.
Chaque cas ou il rendrait un mur de consentement ou un defi anti-robot est un cas
ou le modele chercherait un verbatim dans un texte qui n'en porte aucun, ce qui
est exactement la situation ou il en invente un.
"""

from __future__ import annotations

import httpx
import pytest

from app.extractors import lecteur_relais

_ARTICLE = "Le corps de l'article, assez long pour depasser le seuil. " * 10


@pytest.fixture(autouse=True)
def _relais_actif(monkeypatch):
    monkeypatch.setattr(
        lecteur_relais.settings, "lecture_relais_endpoint", "https://relais.test/{url}"
    )
    monkeypatch.setattr(lecteur_relais.settings, "lecture_relais_api_key", "")


def _relais_simule(monkeypatch, gestionnaire):
    """Branche un transport de test sur le client du module."""
    vrai_client = httpx.AsyncClient

    def _client(**kwargs):
        kwargs.pop("transport", None)
        return vrai_client(transport=httpx.MockTransport(gestionnaire), **kwargs)

    monkeypatch.setattr(lecteur_relais.httpx, "AsyncClient", _client)


@pytest.mark.asyncio
async def test_l_article_est_rendu(monkeypatch):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        assert str(requete.url) == "https://relais.test/https://exemple.org/a"
        return httpx.Response(200, text=_ARTICLE)

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") == _ARTICLE.strip()


@pytest.mark.asyncio
async def test_sans_point_d_entree_aucun_appel_reseau(monkeypatch):
    """Vider le reglage doit vraiment cesser de confier les URL a un tiers."""

    def gestionnaire(requete: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("le relais desactive ne doit appeler personne")

    _relais_simule(monkeypatch, gestionnaire)
    monkeypatch.setattr(lecteur_relais.settings, "lecture_relais_endpoint", "")
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_une_url_vide_n_appelle_personne(monkeypatch):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("appel reseau inattendu")

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("  ") is None


@pytest.mark.asyncio
async def test_une_url_a_accolades_ne_fait_pas_lever(monkeypatch):
    """`str.format` leverait ici ; c'est pourquoi le module fait `str.replace`."""
    cible = "https://exemple.org/a?q={inconnu}"

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_ARTICLE)

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais(cible) == _ARTICLE.strip()


@pytest.mark.asyncio
async def test_le_quota_atteint_ne_leve_pas(monkeypatch):
    """429 est le cas nominal du palier sans clé : il doit passer la main."""

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_un_relais_injoignable_ne_leve_pas(monkeypatch):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("trop long")

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_un_defi_anti_robot_relaye_est_rejete(monkeypatch):
    """Le relais peut avoir recu le mur plutot que la page."""

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="Just a moment... Enable JavaScript and cookies to continue. " * 8,
        )

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_une_reponse_trop_courte_est_rejetee(monkeypatch):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Redirection en cours.")

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_une_erreur_de_l_amont_n_est_pas_du_contenu(monkeypatch):
    """Le relais repond 200 et raconte le 404 de l'amont dans le corps.

    Sans cette lecture, un lien mort arrivait au modele comme un article, et le
    refus qui suivait accusait la citation la ou l'adresse etait fausse.
    """

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "Title: Not Found\n\nURL Source: https://exemple.org/a\n\n"
                "Warning: Target URL returned error 404: Not Found\n\n"
                "Markdown Content:\n" + "Page introuvable. " * 40
            ),
        )

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_une_page_d_erreur_servie_en_200_n_est_pas_du_contenu(monkeypatch):
    """Le cas que le compte rendu d'erreur du relais ne couvre pas.

    Mesure en production le 2026-08-28 : une URL inventee sur lemonde.fr rend
    63 456 caracteres de menus sous le titre « Erreur 404 », et le relais n'a
    rien d'anormal a signaler puisque le site a repondu 200. Seul le titre la
    distingue d'un article.
    """

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "Title: Erreur 404\n\nURL Source: https://exemple.org/absente\n\n"
                "Markdown Content:\n" + "Le journal Services Menu Accueil Abonnez-vous. " * 60
            ),
        )

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/absente") is None


@pytest.mark.asyncio
async def test_un_article_qui_parle_d_erreurs_reste_un_article(monkeypatch):
    """Le titre est court : le prix du filtre precedent doit rester nul ici."""

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="Title: Les 400 coups de la modernite\n\nMarkdown Content:\n" + _ARTICLE
        )

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is not None


@pytest.mark.asyncio
async def test_le_html_brut_est_reduit_a_son_texte(monkeypatch):
    """Un relais mandataire rend la page telle quelle, scripts et styles compris.

    Sans le retrait des `style`, la coquille que ScienceDirect sert aux proxies,
    une police en base64 de 167 601 octets, passait pour un article.
    """
    police = "d09GMgABAAAAAIegABEAAAABpYAAAIc7AAEAAAAAAAAA" * 200

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<!DOCTYPE html><html><head><title>Revue</title>"
                f"<style>@font-face{{src:url(data:binary/octet-stream;base64,{police})}}</style>"
                f"<script>var x = '{police}';</script></head>"
                f"<body><article><p>{_ARTICLE}</p></article></body></html>"
            ),
        )

    _relais_simule(monkeypatch, gestionnaire)
    texte = await lecteur_relais.texte_par_relais("https://exemple.org/a")
    assert texte is not None
    assert "d09GMgAB" not in texte
    assert texte.startswith("Revue Le corps de l'article")


@pytest.mark.asyncio
async def test_une_coquille_sans_texte_est_rejetee(monkeypatch):
    """167 601 octets de police, zero caractere d'article : rien n'a ete lu."""
    police = "d09GMgABAAAAAIegABEAAAABpYAAAIc7AAEAAAAAAAAA" * 400

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<!DOCTYPE html><html><head><title>ScienceDirect</title>"
                f"<style>@font-face{{src:url(data:font/woff2;base64,{police})}}</style>"
                "</head><body></body></html>"
            ),
        )

    _relais_simule(monkeypatch, gestionnaire)
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a") is None


@pytest.mark.asyncio
async def test_le_relais_suivant_prend_la_suite_du_precedent(monkeypatch):
    """La raison d'etre de la chaine : les angles morts ne se recouvrent pas.

    Mesure du 2026-08-28 : le premier relais rend le mur d'Elsevier a chaque
    tentative, et refuse x.com d'office ; le second rend x.com. Reessayer le
    meme relais ne sert a rien, changer d'origine, si.
    """
    vues: list[str] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vues.append(str(requete.url))
        if "premier" in str(requete.url):
            return httpx.Response(200, text="Just a moment... " * 30)
        return httpx.Response(200, text=_ARTICLE)

    _relais_simule(monkeypatch, gestionnaire)
    monkeypatch.setattr(
        lecteur_relais.settings,
        "lecture_relais_endpoint",
        "https://premier.test/{url},https://second.test/?u={url_encode}",
    )
    assert await lecteur_relais.texte_par_relais("https://exemple.org/a?x=1") == _ARTICLE.strip()
    assert vues == [
        "https://premier.test/https://exemple.org/a?x=1",
        "https://second.test/?u=https%3A%2F%2Fexemple.org%2Fa%3Fx%3D1",
    ]


@pytest.mark.asyncio
async def test_le_premier_relais_qui_repond_arrete_la_chaine(monkeypatch):
    vues: list[str] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vues.append(str(requete.url))
        return httpx.Response(200, text=_ARTICLE)

    _relais_simule(monkeypatch, gestionnaire)
    monkeypatch.setattr(
        lecteur_relais.settings,
        "lecture_relais_endpoint",
        "https://premier.test/{url},https://second.test/{url}",
    )
    await lecteur_relais.texte_par_relais("https://exemple.org/a")
    assert vues == ["https://premier.test/https://exemple.org/a"]


@pytest.mark.asyncio
async def test_la_cle_ne_part_qu_au_premier_relais(monkeypatch):
    """Un secret n'a rien a faire chez les replis anonymes de la chaine."""
    vues: list[str | None] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vues.append(requete.headers.get("authorization"))
        return httpx.Response(404)

    _relais_simule(monkeypatch, gestionnaire)
    monkeypatch.setattr(lecteur_relais.settings, "lecture_relais_api_key", "secrete")
    monkeypatch.setattr(
        lecteur_relais.settings,
        "lecture_relais_endpoint",
        "https://premier.test/{url},https://second.test/{url}",
    )
    await lecteur_relais.texte_par_relais("https://exemple.org/a")
    assert vues == ["Bearer secrete", None]


@pytest.mark.asyncio
async def test_la_cle_est_envoyee_quand_elle_existe(monkeypatch):
    vues: list[str | None] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        vues.append(requete.headers.get("authorization"))
        return httpx.Response(200, text=_ARTICLE)

    _relais_simule(monkeypatch, gestionnaire)
    await lecteur_relais.texte_par_relais("https://exemple.org/a")
    monkeypatch.setattr(lecteur_relais.settings, "lecture_relais_api_key", "secrete")
    await lecteur_relais.texte_par_relais("https://exemple.org/a")
    assert vues == [None, "Bearer secrete"]
