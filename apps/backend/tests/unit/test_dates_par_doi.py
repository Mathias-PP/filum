"""Une source sans date mais porteuse d'un DOI se date par sa notice Crossref."""

from __future__ import annotations

import pytest

from app.extractors import url_extractor
from app.extractors.url_extractor import ExtractedMetadata
from app.mcp_server import tools_write
from app.mcp_server.tools_write import _resoudre_metadonnees, add_source, create_card
from app.scripts.assainir_sources import dater


@pytest.fixture
def crossref(monkeypatch):
    demandes: list[str] = []

    async def notice(doi):
        demandes.append(doi)
        return ExtractedMetadata(title="Etude", published_at="2019-05-01", journal="Nature")

    monkeypatch.setattr(url_extractor, "crossref_lookup", notice)
    return demandes


@pytest.mark.asyncio
async def test_une_page_sans_date_se_date_par_le_doi_de_son_adresse(crossref, monkeypatch):
    async def page(origine, *, url, doi):
        return ExtractedMetadata(title="Etude")

    monkeypatch.setattr(tools_write.metadonnees_source, "resoudre", page)
    retenues, _ecarts = await _resoudre_metadonnees(
        "page", url="https://doi.org/10.1000/xyz", doi=None, propose={}
    )
    assert retenues["published_at"] == "2019-05-01"
    assert retenues["journal"] == "Nature"
    assert crossref == ["10.1000/xyz"]


@pytest.mark.asyncio
async def test_les_sources_deja_en_base_sans_date_sont_datees(
    db_session, test_user, crossref, monkeypatch
):
    async def existe(url, doi):
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    await create_card(db_session, test_user, slug="dates", title="Dates", card_kind="sujet")
    await add_source(
        db_session,
        test_user,
        card_slug="dates",
        metadata_from="createur",
        title="Etude",
        url="https://doi.org/10.1000/xyz",
    )

    a_dater = await dater(db_session, ecrire=False, lire_pages=False)
    assert [date for _fiche, _source, date in a_dater] == ["2019-05-01"]
    await dater(db_session, ecrire=True, lire_pages=False)
    assert await dater(db_session, ecrire=False, lire_pages=False) == []
