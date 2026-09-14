"""La grille de relecture nomme ce qui manque a une fiche, et l'etape qui le comble."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, create_card
from app.models.source import Source
from app.services import excerpt_insertion, relecture
from app.services.relecture import grille

PASSAGE = (
    "Le Conseil constitutionnel juge que le droit de greve s'exerce dans le cadre des "
    "lois qui le reglementent."
)
PAGE = f"Decision du Conseil constitutionnel. {PASSAGE} La decision precise ensuite ses limites."


@pytest.fixture
async def fiche(db_session, test_user, monkeypatch):
    async def existe(url, doi):
        return None

    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    await create_card(
        db_session, test_user, slug="droit-de-greve", title="Droit de grève", card_kind="sujet"
    )
    return "droit-de-greve"


async def _poser(db_session, test_user, fiche, url, *, extrait: bool) -> str:
    rendu = await add_source(
        db_session,
        test_user,
        card_slug=fiche,
        metadata_from="createur",
        title="Decision",
        url=url,
        excerpts=[{"text": PASSAGE, "context": "Cadre legal de la greve"}] if extrait else None,
    )
    return rendu["id"]


async def _source(db_session, source_id: str) -> Source:
    requete = select(Source).where(Source.id == UUID(source_id))
    return (await db_session.execute(requete)).scalar_one()


def _genres(manques) -> list[tuple[str, str]]:
    return [(m.genre, m.etape) for m in manques]


@pytest.mark.asyncio
async def test_une_source_sans_extrait_est_un_manque_renvoye_a_l_exploration(
    db_session, test_user, fiche
):
    source_id = await _poser(
        db_session, test_user, fiche, "https://exemple.test/nue", extrait=False
    )
    manques = await grille(db_session, test_user.id, fiche)
    assert (relecture.SOURCE_SANS_EXTRAIT, "exploration") in _genres(manques)
    assert any(source_id in m.cible for m in manques)


@pytest.mark.asyncio
async def test_une_source_citee_sans_position_est_renvoyee_aux_positions(
    db_session, test_user, fiche
):
    await _poser(db_session, test_user, fiche, "https://exemple.test/a", extrait=True)
    manques = await grille(db_session, test_user.id, fiche)
    assert (relecture.SOURCE_SANS_POSITION, "positions") in _genres(manques)
    assert (relecture.SANS_NUANCE, "exploration") in _genres(manques)


@pytest.mark.asyncio
async def test_une_nuance_posee_efface_le_manque(db_session, test_user, fiche):
    source_id = await _poser(db_session, test_user, fiche, "https://exemple.test/a", extrait=True)
    (await _source(db_session, source_id)).stance = "nuance-contredit"
    await db_session.commit()
    assert await grille(db_session, test_user.id, fiche) == []


@pytest.mark.asyncio
async def test_une_source_retractee_en_appui_est_un_manque(db_session, test_user, fiche):
    source_id = await _poser(db_session, test_user, fiche, "https://exemple.test/a", extrait=True)
    source = await _source(db_session, source_id)
    source.stance = "appuie"
    source.retraction_status = "retracted"
    await db_session.commit()
    assert (relecture.RETRACTATION, "positions") in _genres(
        await grille(db_session, test_user.id, fiche)
    )


@pytest.mark.asyncio
async def test_un_lien_vers_une_fiche_philum_n_est_pas_un_manque(db_session, test_user, fiche):
    await create_card(db_session, test_user, slug="voisine", title="Voisine", card_kind="sujet")
    await _poser(
        db_session,
        test_user,
        fiche,
        f"http://localhost:5173/@{test_user.username}/voisine",
        extrait=False,
    )
    assert await grille(db_session, test_user.id, fiche) == []


@pytest.mark.asyncio
async def test_une_fiche_inconnue_n_a_pas_de_manque(db_session, test_user):
    assert await grille(db_session, test_user.id, "inexistante") == []
