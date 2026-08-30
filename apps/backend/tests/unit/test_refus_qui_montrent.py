"""Un identifiant fautif rend ce qui existe, pas un refus nu.

Mesure en production : un refus qui ne montre rien fait reessayer le meme
identifiant, ou en fabriquer un autre. Un refus qui montre la liste se corrige
au meme tour. Ce que ces tests verrouillent, c'est la presence de la matiere
dans le message, pas sa mise en forme.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import (
    add_excerpt,
    add_source,
    create_card,
    delete_excerpt,
    update_source,
)


@pytest_asyncio.fixture
async def fiche(db_session, test_user):
    return await create_card(
        db_session,
        test_user,
        slug="fiche-des-refus",
        title="Fiche pour les refus qui montrent",
        content_url="https://example.org/video",
    )


@pytest.mark.asyncio
async def test_un_slug_fautif_rend_les_fiches(db_session, test_user, fiche):
    with pytest.raises(ToolError) as capture:
        await add_source(db_session, test_user, card_slug="fiche-des-refuz", url="https://x.test/")
    message = str(capture.value)
    assert "fiche-des-refus" in message
    assert "Fiche pour les refus qui montrent" in message


@pytest.mark.asyncio
async def test_sans_aucune_fiche_le_refus_dit_par_ou_commencer(db_session, test_user):
    with pytest.raises(ToolError, match="create_card"):
        await add_source(db_session, test_user, card_slug="jamais-creee", url="https://x.test/")


@pytest.mark.asyncio
async def test_un_identifiant_de_source_fautif_rend_les_sources(db_session, test_user, fiche):
    posee = await add_source(
        db_session,
        test_user,
        card_slug="fiche-des-refus",
        url="https://exemple.test/article",
        title="Un article reel",
    )
    with pytest.raises(ToolError) as capture:
        await update_source(
            db_session,
            test_user,
            source_id="00000000-0000-0000-0000-000000000000",
            title="Peu importe",
        )
    message = str(capture.value)
    assert posee["id"] in message
    assert "Un article reel" in message
    assert "fiche-des-refus" in message


@pytest.mark.asyncio
async def test_un_identifiant_d_extrait_fautif_rend_les_extraits(
    db_session, test_user, fiche, monkeypatch
):
    from app.services import excerpt_insertion

    async def _page(url):
        return ("Le passage exact que porte la source, pose pour ce test.", False, True)

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", _page)

    posee = await add_source(
        db_session,
        test_user,
        card_slug="fiche-des-refus",
        url="https://exemple.test/article",
        title="Un article reel",
    )
    extrait = await add_excerpt(
        db_session,
        test_user,
        source_id=posee["id"],
        text="Le passage exact que porte la source, pose pour ce test.",
        title="Le passage",
    )
    with pytest.raises(ToolError) as capture:
        await delete_excerpt(
            db_session,
            test_user,
            source_id=posee["id"],
            excerpt_id="00000000-0000-0000-0000-000000000000",
        )
    message = str(capture.value)
    assert extrait["id"] in message
    assert "Le passage" in message


@pytest.mark.asyncio
async def test_une_source_sans_extrait_le_dit(db_session, test_user, fiche):
    posee = await add_source(
        db_session,
        test_user,
        card_slug="fiche-des-refus",
        url="https://exemple.test/article",
        title="Un article reel",
    )
    with pytest.raises(ToolError, match="aucun extrait"):
        await delete_excerpt(
            db_session,
            test_user,
            source_id=posee["id"],
            excerpt_id="00000000-0000-0000-0000-000000000000",
        )
