"""Une IA n'ajoute une source qu'avec un extrait retrouve ; le createur, toujours.

Mesure du 2026-09-13 : le deroule posait les sources a une etape et cherchait
leurs extraits a la suivante, et une source sans passage retrouve restait vide
dans la fiche. L'agent du chat et le serveur MCP refusent donc une source sans
extrait retrouve. L'interface, elle, laisse le createur en poser une pour la
completer plus tard.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent_tools import philum
from app.agent_tools.tool import ToolContext
from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, add_sources_batch, create_card
from app.models.source import Source
from app.services import excerpt_insertion

PASSAGE = (
    "Les exemptions industrielles ont limite l'effet de la taxe sur l'industrie "
    "lourde jusqu'en 2018."
)
PAGE = f"La taxe carbone suedoise a ete introduite en 1991. {PASSAGE}"
EXTRAIT = {"text": PASSAGE, "context": "Effet de la taxe carbone suedoise sur l'industrie"}


@pytest.fixture
async def fiche(db_session, test_user, monkeypatch):
    async def existe(url, doi):
        return None

    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    await create_card(db_session, test_user, slug="taxe", title="Taxe carbone", card_kind="sujet")
    return "taxe"


def _agent(nom: str):
    return next(t for t in philum.philum_tools() if t.name == nom)


def _ctx(db_session, test_user) -> ToolContext:
    return ToolContext(db=db_session, user=test_user, creator_id=test_user.id, session_id=None)


def _source(url: str, **extra) -> dict:
    return {"metadata_from": "createur", "title": "Taxe carbone suedoise", "url": url, **extra}


async def _sources(db_session) -> list[Source]:
    lignes = await db_session.execute(select(Source).where(Source.deleted_at.is_(None)))
    return list(lignes.scalars())


@pytest.mark.asyncio
async def test_l_agent_ne_pose_pas_de_source_sans_extrait(db_session, test_user, fiche):
    rendu = await _agent("add_source").execute(
        _ctx(db_session, test_user), {"card_slug": fiche, **_source("https://exemple.test/a")}
    )
    assert "propose_passages" in rendu["error"]
    assert await _sources(db_session) == []


@pytest.mark.asyncio
async def test_des_extraits_tous_introuvables_n_ecrivent_rien(db_session, test_user, fiche):
    rendu = await _agent("add_source").execute(
        _ctx(db_session, test_user),
        {
            "card_slug": fiche,
            **_source(
                "https://exemple.test/a",
                excerpts=[
                    {"text": "Une phrase que la page ne porte nulle part, ni de pres ni de loin."}
                ],
            ),
        },
    )
    assert "Extraits refuses" in rendu["error"]
    assert await _sources(db_session) == []


@pytest.mark.asyncio
async def test_un_extrait_retrouve_fait_entrer_la_source(db_session, test_user, fiche):
    rendu = await _agent("add_source").execute(
        _ctx(db_session, test_user),
        {"card_slug": fiche, **_source("https://exemple.test/a", excerpts=[EXTRAIT])},
    )
    assert "error" not in rendu
    assert rendu["excerpts"]
    assert len(await _sources(db_session)) == 1


@pytest.mark.asyncio
async def test_le_modele_ne_peut_pas_lever_l_exigence(db_session, test_user, fiche):
    outil = _agent("add_source")
    assert "exiger_extrait" not in outil.parameters["properties"]
    rendu = await outil.execute(
        _ctx(db_session, test_user),
        {"card_slug": fiche, "exiger_extrait": False, **_source("https://exemple.test/a")},
    )
    assert "exiger_extrait" in rendu["error"]
    assert await _sources(db_session) == []


@pytest.mark.asyncio
async def test_le_createur_pose_toujours_une_source_sans_extrait(db_session, test_user, fiche):
    rendu = await add_source(
        db_session, test_user, card_slug=fiche, **_source("https://exemple.test/a")
    )
    assert rendu["id"]
    assert len(await _sources(db_session)) == 1


@pytest.mark.asyncio
async def test_un_lien_vers_une_fiche_philum_passe_sans_extrait(db_session, test_user, fiche):
    await create_card(db_session, test_user, slug="voisine", title="Voisine", card_kind="sujet")
    rendu = await add_source(
        db_session,
        test_user,
        card_slug=fiche,
        exiger_extrait=True,
        **_source(f"http://localhost:5173/@{test_user.username}/voisine"),
    )
    assert rendu["id"]


@pytest.mark.asyncio
async def test_un_lot_d_ia_ecarte_les_entrees_sans_extrait(db_session, test_user, fiche):
    rendu = await add_sources_batch(
        db_session,
        test_user,
        card_slug=fiche,
        exiger_extrait=True,
        sources=[
            _source("https://exemple.test/nue"),
            _source("https://exemple.test/citee", excerpts=[EXTRAIT]),
        ],
    )
    assert [e["index"] for e in rendu["failed"]] == [0]
    assert "extrait" in rendu["failed"][0]["reason"]
    assert len(rendu["created"]) == 1 and rendu["created"][0]["excerpts"]
    assert [s.url for s in await _sources(db_session)] == ["https://exemple.test/citee"]


@pytest.mark.asyncio
async def test_un_lot_du_createur_reste_libre(db_session, test_user, fiche):
    rendu = await add_sources_batch(
        db_session, test_user, card_slug=fiche, sources=[_source("https://exemple.test/nue")]
    )
    assert len(rendu["created"]) == 1 and rendu["failed"] == []
