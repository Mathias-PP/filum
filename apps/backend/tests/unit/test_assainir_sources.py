"""Les sources posees avant la regle des titres sont corrigees par une passe rejouable."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.extractors.url_extractor import ExtractedMetadata
from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, create_card
from app.models.source import Source
from app.scripts import assainir_sources
from app.scripts.assainir_sources import assainir

PMC = "https://pmc.ncbi.nlm.nih.gov/articles/PMC6419978/"


@pytest.fixture
async def source_ancienne(db_session, test_user, monkeypatch):
    """Une source dont le titre et l'auteur ont ete inscrits avant la regle."""

    async def existe(url, doi):
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    await create_card(
        db_session, test_user, slug="adenomyose", title="Adénomyose", card_kind="sujet"
    )
    rendu = await add_source(
        db_session,
        test_user,
        card_slug="adenomyose",
        metadata_from="createur",
        title="Titre provisoire",
        url=PMC,
    )
    # Ecriture SQL directe : c'est ainsi que les lignes d'avant la regle existent.
    await db_session.execute(
        text("UPDATE sources SET title = :t, authors = :a WHERE url = :u"),
        {
            "t": "Checking your browser - reCAPTCHA",
            "a": "https://www.facebook.com/inserm.fr",
            "u": PMC,
        },
    )
    await db_session.commit()
    db_session.expire_all()
    return rendu["id"]


async def _lire(db_session) -> Source:
    return (await db_session.execute(select(Source).where(Source.url == PMC))).scalar_one()


@pytest.mark.asyncio
async def test_sans_ecrire_la_passe_liste_sans_rien_changer(db_session, source_ancienne):
    corrections = await assainir(db_session, ecrire=False, resoudre=False)
    assert [c.ecarts() for c in corrections] == [
        {
            "title": ("Checking your browser - reCAPTCHA", None),
            "authors": ("https://www.facebook.com/inserm.fr", None),
        }
    ]
    db_session.expire_all()
    assert (await _lire(db_session)).title == "Checking your browser - reCAPTCHA"


@pytest.mark.asyncio
async def test_la_passe_corrige_la_nature_et_retrouve_le_doi_pubmed(
    db_session, source_ancienne, monkeypatch
):
    # Une ligne d'avant la regle de nature : un article PMC classe « page-web / individu ».
    await db_session.execute(
        text("UPDATE sources SET category = 'page-web', author_kind = 'individu', doi = NULL")
    )
    await db_session.commit()
    db_session.expire_all()

    async def doi_ncbi(url):
        return "10.12688/f1000research.17242.1"

    async def resoudre(origine, *, url, doi):
        return None

    monkeypatch.setattr(assainir_sources, "resolve_doi_from_pubmed", doi_ncbi)
    monkeypatch.setattr(assainir_sources.metadonnees_source, "resoudre", resoudre)
    await assainir(db_session, ecrire=True, resoudre=True)
    db_session.expire_all()

    source = await _lire(db_session)
    assert source.doi == "10.12688/f1000research.17242.1"
    assert (source.category, source.author_kind) == ("article-scientifique", "chercheur")


@pytest.mark.asyncio
async def test_la_passe_vide_ce_qui_n_est_pas_un_titre(db_session, source_ancienne):
    await assainir(db_session, ecrire=True, resoudre=False)
    db_session.expire_all()
    source = await _lire(db_session)
    assert source.title is None
    assert source.authors is None
    # Rejouer ne trouve plus rien.
    assert await assainir(db_session, ecrire=True, resoudre=False) == []


@pytest.mark.asyncio
async def test_avec_resoudre_le_vrai_titre_est_retrouve(db_session, source_ancienne, monkeypatch):
    async def resoudre(origine, *, url, doi):
        assert origine == "page"
        return ExtractedMetadata(
            title="Recent advances in understanding and managing adenomyosis",
            authors="Vannuccini S., Petraglia F.",
        )

    monkeypatch.setattr(assainir_sources.metadonnees_source, "resoudre", resoudre)
    await assainir(db_session, ecrire=True, resoudre=True)
    db_session.expire_all()
    source = await _lire(db_session)
    assert source.title == "Recent advances in understanding and managing adenomyosis"
    assert source.authors == "Vannuccini S., Petraglia F."
