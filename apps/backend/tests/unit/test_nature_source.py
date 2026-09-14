"""La nature d'une source suit les faits, sans ecraser un choix du createur.

Cas mesures le 2026-09-14 sur la base de production.
"""

from __future__ import annotations

import pytest

from app.core.nature_source import nature_corrigee
from app.models.source import Source


def _nature(url, *, doi=None, journal=None, fmt="texte", cat="page-web", auteur="individu"):
    n = nature_corrigee(
        url=url, doi=doi, journal=journal, format=fmt, category=cat, author_kind=auteur
    )
    return (n.format, n.category, n.author_kind)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.who.int/fr/news-room/fact-sheets/detail/endometriosis",
        "https://www.inserm.fr/dossier/endometriose/",
        "https://www.ameli.fr/assure/sante/themes/regles-douloureuses/douleurs-regles",
        "https://www.sante.fr/comprendre-lendometriose",
        "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000886460",
        "https://www.padil.gov.au/pests-and-diseases/pest/main/136430",
        "https://www.fao.org/3/y4011e/y4011e00.htm",
        "https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32016R0679",
    ],
)
def test_un_organisme_public_n_est_pas_un_individu(url):
    assert _nature(url) == ("texte", "page-web", "institution-publique")


@pytest.mark.parametrize(
    "url", ["https://ipm.ucanr.edu/agriculture/thrips/", "https://www.nhm.ac.uk/discover.html"]
)
def test_une_universite_n_est_pas_un_individu(url):
    assert _nature(url)[2] == "ecole"


def test_une_video_youtube_n_est_pas_du_texte():
    assert _nature("https://youtu.be/Sk7Ia2Lsuak") == ("video", "page-web", "individu")


@pytest.mark.parametrize(
    ("url", "doi", "attendu"),
    [
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC6419978/", None, "article-scientifique"),
        ("https://exemple.org/revue/article", "10.1000/xyz", "article-scientifique"),
        ("https://arxiv.org/abs/2401.00001", None, "preprint"),
    ],
)
def test_un_article_se_reconnait_a_son_doi_ou_a_son_hebergeur(url, doi, attendu):
    assert _nature(url, doi=doi)[1:] == (attendu, "chercheur")


def test_un_choix_informatif_du_createur_n_est_jamais_ecrase():
    assert _nature("https://www.inserm.fr/actualite/x", cat="article-presse", auteur="media") == (
        "texte",
        "article-presse",
        "media",
    )
    assert _nature("https://youtu.be/abc", fmt="audio") == ("audio", "page-web", "individu")


@pytest.mark.parametrize(
    "url",
    [
        "https://filum-eight.vercel.app/@createur/fiche",
        "https://en.wikipedia.org/wiki/Endometriosis",
        "https://www.endofrance.org",
        "https://acme.com/blog",
        "",
    ],
)
def test_sans_indice_la_valeur_neutre_reste(url):
    assert _nature(url) == ("texte", "page-web", "individu")


@pytest.mark.asyncio
async def test_le_modele_applique_la_regle_a_l_enregistrement(db_session, test_user):
    from app.mcp_server.tools_write import create_card

    carte = await create_card(
        db_session, test_user, slug="nature", title="Nature", card_kind="sujet"
    )
    from sqlalchemy import select

    from app.models.biblio_card import BiblioCard

    fiche = (
        await db_session.execute(select(BiblioCard).where(BiblioCard.slug == carte["slug"]))
    ).scalar_one()
    source = Source(
        biblio_card_id=fiche.id,
        url="https://www.who.int/fr/news-room/fact-sheets/detail/endometriosis",
        format="texte",
        category="page-web",
        author_kind="individu",
    )
    db_session.add(source)
    await db_session.commit()
    assert source.author_kind == "institution-publique"

    source.url = "https://youtu.be/Sk7Ia2Lsuak"
    await db_session.commit()
    assert source.format == "video"
