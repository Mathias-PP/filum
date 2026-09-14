"""Une seule lecture de page nomme la source, par la premiere voie qui la rend.

Mesures du 2026-09-14 : ameli.fr refuse la VM et le relais, l'archive porte la
page ; le modele nommait les auteurs Inserm que la lecture de la page ignorait.
"""

from __future__ import annotations

import pytest

from app.extractors import lecture_page
from app.extractors.lecture_page import auteurs_lus, lu_dans, metadonnees_de_la_page
from app.extractors.url_extractor import ExtractedMetadata, _looks_like_challenge_page
from app.services import llm
from app.services.llm import LlmSourceMetadata

AMELI = "https://www.ameli.fr/assure/sante/themes/regles-douloureuses/douleurs-regles"
MUR_AMELI = (
    "Vérification de sécurité L’Assurance Maladie vous invite à prouver que vous êtes un "
    "être humain en cochant la case ci-dessous."
)
CAPTURE = (
    "<html><head><title>Douleurs pendant les règles ou dysménorrhée : quelles sont les causes ? "
    "| ameli.fr | Assuré</title></head><body>" + "Les règles douloureuses. " * 30 + "</body></html>"
)


@pytest.fixture
def voies(monkeypatch):
    """Chaque voie repond ce que le test lui fait dire ; aucune n'appelle le reseau."""
    etat = {"directe": None, "relais": None, "archive": None, "modele": None}

    async def directe(url):
        return etat["directe"]

    async def relais(url):
        return etat["relais"]

    async def archive(url):
        return etat["archive"]

    async def modele(texte, url):
        return etat["modele"]

    monkeypatch.setattr(lecture_page.url_extractor, "_html_scrape", directe)
    monkeypatch.setattr(lecture_page, "page_par_relais", relais)
    monkeypatch.setattr(lecture_page, "html_archive", archive)
    monkeypatch.setattr(llm, "extract_metadata", modele)
    return etat


def test_le_mur_d_ameli_est_reconnu_comme_obstacle():
    assert _looks_like_challenge_page("Vérification de sécurité", MUR_AMELI)


@pytest.mark.asyncio
async def test_une_page_refusee_est_nommee_par_son_archive(voies):
    voies["directe"] = ExtractedMetadata(access_blocked=True)
    voies["archive"] = CAPTURE

    meta = await metadonnees_de_la_page(AMELI)

    assert meta is not None
    assert meta.title == "Douleurs pendant les règles ou dysménorrhée : quelles sont les causes ?"


@pytest.mark.asyncio
async def test_le_relais_passe_avant_l_archive(voies):
    voies["directe"] = ExtractedMetadata(access_blocked=True)
    voies["relais"] = ("Le budget de la commune | Mairie", "Le conseil municipal a vote. " * 20)
    voies["archive"] = CAPTURE

    meta = await metadonnees_de_la_page("https://mairie.example/budget")
    assert meta is not None and meta.title.startswith("Le budget de la commune")


@pytest.mark.asyncio
async def test_sans_aucune_voie_le_refus_reste_dit(voies):
    voies["directe"] = ExtractedMetadata(access_blocked=True)
    meta = await metadonnees_de_la_page(AMELI)
    assert meta is not None and meta.access_blocked and meta.title is None


@pytest.mark.asyncio
async def test_les_auteurs_du_modele_ne_sont_gardes_que_s_ils_figurent_dans_la_page(voies):
    texte = (
        "Dossier mis à jour avec Daniel Vaiman, responsable d'équipe, Ludivine Doridot "
        "et Marina Kvaskoff. " + "L'endométriose touche une femme sur dix. " * 10
    )
    voies["directe"] = ExtractedMetadata(title="Endométriose", page_text=texte)
    voies["modele"] = LlmSourceMetadata(
        authors="Daniel Vaiman, Ludivine Doridot, Marina Kvaskoff, Jean Invente",
        title="Un titre que la page ne porte pas",
    )

    meta = await metadonnees_de_la_page("https://www.inserm.fr/dossier/endometriose/")

    assert meta is not None
    assert meta.authors == "Daniel Vaiman, Ludivine Doridot, Marina Kvaskoff"
    assert meta.title == "Endométriose"


def test_la_recherche_ignore_blancs_casse_et_apostrophes():
    assert lu_dans("Guerre d’Algérie", "La  guerre\nd'algérie commence en 1954.")
    assert not lu_dans("Guerre de Crimée", "La guerre d'Algérie commence en 1954.")
    assert auteurs_lus("A. Dupont et B. Martin", "Par B. Martin.") == "B. Martin"
