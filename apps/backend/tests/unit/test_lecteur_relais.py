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
