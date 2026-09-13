"""Un refus d'extrait doit montrer quoi copier.

Mesure du 2026-09-13 : 73 refus sur 83 appels a `add_excerpt` dans une seule
conversation. Le refus ne montrait rien de la page, et le modele reecrivait sa
paraphrase au lieu de la relire.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import add_excerpt, add_source, create_card, find_passage
from app.services import excerpt_insertion
from app.services.excerpt_insertion import passages_proches

PAGE = (
    "Avant le passage utile, quelques phrases de contexte editorial. "
    "La memoire n'est pas un enregistrement, c'est une reconstruction. "
    "Apres le passage utile, la page continue sur un autre sujet."
)
PASSAGE = "La memoire n'est pas un enregistrement, c'est une reconstruction."
PARAPHRASE = "Reconstruction : voila ce qu'est la memoire, et non un enregistrement."


def test_le_passage_le_plus_proche_est_une_tranche_exacte_de_la_page():
    proches = passages_proches(PAGE, PARAPHRASE)
    assert proches[0] == PASSAGE
    assert all(p in PAGE for p in proches)


def test_rien_de_commun_rien_de_propose():
    assert passages_proches(PAGE, "Les mitochondries produisent l'energie cellulaire.") == []


def test_un_long_passage_est_coupe_a_un_mot_et_reste_verbatim():
    page = "Premiere phrase. " + " ".join(["memoire reconstruction enregistrement"] * 60) + "."
    proches = passages_proches(page, "memoire reconstruction enregistrement")
    assert proches
    assert len(proches[0]) <= 500
    assert proches[0] in page


@pytest.fixture
async def source(db_session, test_user, monkeypatch):
    async def _page(_url):
        return PAGE, False, True

    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", _page)
    card = await create_card(db_session, test_user, slug="proches", title="Proches")
    return await add_source(
        db_session,
        test_user,
        metadata_from="createur",
        card_slug=card["slug"],
        title="Une source lisible",
        url="https://example.org/proches",
    )


@pytest.mark.asyncio
async def test_find_passage_rend_ce_qu_add_excerpt_accepte(db_session, test_user, source):
    trouve = await find_passage(db_session, test_user, source_id=source["id"], query=PARAPHRASE)
    assert trouve["passages"][0] == PASSAGE

    pose = await add_excerpt(
        db_session, test_user, source_id=source["id"], text=trouve["passages"][0]
    )
    assert pose["verified_status"] == "found"


@pytest.mark.asyncio
async def test_find_passage_dit_quand_rien_ne_ressemble(db_session, test_user, source):
    trouve = await find_passage(
        db_session, test_user, source_id=source["id"], query="mitochondries energie cellulaire"
    )
    assert trouve["passages"] == []
    assert "pas dans cette source" in trouve["message"]


@pytest.mark.asyncio
async def test_le_refus_montre_quoi_copier(db_session, test_user, source):
    with pytest.raises(ToolError) as refus:
        await add_excerpt(db_session, test_user, source_id=source["id"], text=PARAPHRASE)
    assert PASSAGE in str(refus.value)
