from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def published_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="memoire-cerveau",
        title="Memoire et cerveau",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://doi.org/10.1000/exemple",
        title="Etude exemple",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()
    return card, source


@pytest.mark.asyncio
async def test_search_cards_finds_by_title(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="memoire")
    assert len(results) == 1
    assert results[0]["creator"] == test_user.username
    assert results[0]["slug"] == "memoire-cerveau"
    assert "sources" not in results[0]


@pytest.mark.asyncio
async def test_search_cards_ignores_drafts(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards
    from app.models.biblio_card import BiblioCard

    draft = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon",
        title="Memoire brouillon",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(draft)
    await db_session.commit()
    results = await search_cards(db_session, query="memoire")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_card_returns_compact_sources(db_session, published_card, test_user):
    from app.mcp_server.tools import get_card

    card_dict = await get_card(db_session, creator=test_user.username, slug="memoire-cerveau")
    assert card_dict["title"] == "Memoire et cerveau"
    assert len(card_dict["sources"]) == 1
    src = card_dict["sources"][0]
    assert src["url"] == "https://doi.org/10.1000/exemple"
    assert "annotation" not in src


@pytest.mark.asyncio
async def test_get_card_unknown_returns_none(db_session):
    from app.mcp_server.tools import get_card

    assert await get_card(db_session, creator="nobody", slug="nope") is None


@pytest.mark.asyncio
async def test_get_source_detail(db_session, published_card):
    from app.mcp_server.tools import get_source

    _, source = published_card
    detail = await get_source(db_session, source_id=str(source.id))
    assert detail["title"] == "Etude exemple"
    assert detail["category"] == "article-scientifique"


@pytest.mark.asyncio
async def test_get_source_of_draft_card_returns_none(db_session, test_user):
    from app.mcp_server.tools import get_source
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    draft = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon-fuite",
        title="Brouillon prive",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(draft)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=draft.id,
        position=0,
        url="https://example.org/secret",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()

    assert await get_source(db_session, source_id=str(source.id)) is None


@pytest_asyncio.fixture
async def private_published_card(db_session, test_user):
    """Fiche publiee mais gardee privee : le web public ne doit jamais la voir.

    « Publiee » decrit l'etat du travail, pas l'audience. Une fiche peut etre
    terminee et signee sans etre offerte au monde ; c'est `visibility` qui
    tranche, et toutes les routes REST publiques le verifient.
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="dossier-confidentiel",
        title="Memoire dossier confidentiel",
        content_type="video",
        platform="youtube",
        status="published",
        visibility="private",
    )
    db_session.add(card)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://example.org/piece-confidentielle",
        title="Piece confidentielle",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()
    return card, source


@pytest.mark.asyncio
async def test_search_cards_ignores_private_cards(db_session, private_published_card):
    from app.mcp_server.tools import search_cards

    assert await search_cards(db_session, query="memoire") == []


@pytest.mark.asyncio
async def test_get_card_private_returns_none(db_session, private_published_card, test_user):
    from app.mcp_server.tools import get_card

    assert (
        await get_card(db_session, creator=test_user.username, slug="dossier-confidentiel") is None
    )


@pytest.mark.asyncio
async def test_get_source_of_private_card_returns_none(db_session, private_published_card):
    from app.mcp_server.tools import get_source

    _, source = private_published_card
    assert await get_source(db_session, source_id=str(source.id)) is None


@pytest.mark.asyncio
async def test_find_cards_citing_ignores_private_cards(db_session, private_published_card):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://example.org/piece-confidentielle")
    assert results == []


@pytest.mark.asyncio
async def test_search_cards_escapes_like_wildcards(db_session, published_card):
    from app.mcp_server.tools import search_cards

    assert await search_cards(db_session, query="%") == []
    assert await search_cards(db_session, query="_emoire") == []


@pytest_asyncio.fixture
async def fiche_decrite(db_session, test_user):
    """Une fiche dont le sujet ne figure que hors du titre.

    C'est le cas qui separait l'agent de l'humain : sur ce corpus, une requete
    « hippocampe » ne rendait rien au MCP alors que /discover trouvait la fiche.
    """
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="episode-42",
        title="Episode 42",
        description="Une plongee dans l'hippocampe et la consolidation des souvenirs.",
        content_authors="Bruce Benamran",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.commit()
    return card


@pytest.mark.asyncio
async def test_search_cards_cherche_dans_la_description(db_session, fiche_decrite):
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="hippocampe")
    assert [r["slug"] for r in results] == ["episode-42"]


@pytest.mark.asyncio
async def test_search_cards_cherche_l_auteur_du_contenu(db_session, fiche_decrite):
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="benamran")
    assert [r["slug"] for r in results] == ["episode-42"]


@pytest.mark.asyncio
async def test_search_cards_cherche_le_nom_affiche_du_createur(
    db_session, fiche_decrite, test_user
):
    from app.mcp_server.tools import search_cards

    test_user.display_name = "Lea Marchand"
    await db_session.commit()
    results = await search_cards(db_session, query="marchand")
    assert [r["slug"] for r in results] == ["episode-42"]


@pytest.mark.asyncio
async def test_search_cards_cherche_dans_la_bibliographie(db_session, published_card, test_user):
    """Un agent cherche un travail cite, pas un titre de fiche.

    La fiche s'appelle « Memoire et cerveau » et cite « Etude exemple » :
    chercher « etude » ne ramenait rien, alors que c'est exactement la question
    que le corpus existe pour repondre.
    """
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="etude exemple")
    assert [r["slug"] for r in results] == ["memoire-cerveau"]


@pytest.mark.asyncio
async def test_search_cards_cherche_l_auteur_d_une_source(db_session, published_card):
    from app.mcp_server.tools import search_cards

    _, source = published_card
    source.authors = "Elizabeth F. Loftus"
    await db_session.commit()
    results = await search_cards(db_session, query="loftus")
    assert [r["slug"] for r in results] == ["memoire-cerveau"]


@pytest.mark.asyncio
async def test_une_fiche_qui_cite_deux_fois_reste_une_fiche(db_session, published_card, test_user):
    """Une jointure la dedoublerait, et l'agent croirait a deux fiches."""
    from uuid import uuid4 as _uuid4

    from app.mcp_server.tools import search_cards
    from app.models.source import Source

    card, _ = published_card
    db_session.add(
        Source(
            id=_uuid4(),
            biblio_card_id=card.id,
            position=1,
            url="https://doi.org/10.1000/second",
            title="Etude exemple, seconde partie",
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
        )
    )
    await db_session.commit()
    assert len(await search_cards(db_session, query="etude exemple")) == 1


@pytest_asyncio.fixture
async def source_complete(db_session, test_user):
    """Une source qui a tout a dire : verbatim, position declaree, retractation.

    C'est le cas ou le MCP se jugeait : un agent qui n'obtient ni les extraits
    ni l'etat de retractation en sait moins que n'importe qui telechargeant le
    CSV, et citera comme valide une reference retiree.
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source
    from app.models.source_excerpt import SourceExcerpt

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-complete",
        title="Fiche complete",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://example.org/etude",
        title="Etude retiree",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
        doi="10.1000/retiree",
        journal="Revue Exemple",
        stance="nuance-contredit",
        retraction_status="retracted",
        retraction_notice_doi="10.1000/avis",
        oa_status="gold",
        oa_url="https://example.org/pdf",
    )
    db_session.add(source)
    await db_session.flush()
    db_session.add(
        SourceExcerpt(
            id=uuid4(),
            source_id=source.id,
            position=0,
            text="Ce que la source dit.",
            title="Le point central",
            context="Extrait de la discussion finale.",
            annotated_by_ai=True,
        )
    )
    await db_session.commit()
    return source


@pytest.mark.asyncio
async def test_get_source_porte_le_verbatim(db_session, source_complete):
    from app.mcp_server.tools import get_source

    detail = await get_source(db_session, source_id=str(source_complete.id))
    assert len(detail["excerpts"]) == 1
    extrait = detail["excerpts"][0]
    assert extrait["text"] == "Ce que la source dit."
    assert extrait["title"] == "Le point central"
    assert extrait["context"] == "Extrait de la discussion finale."
    assert extrait["annotated_by_ai"] is True
    #: `null` = jamais relu, pas « relu et introuvable ».
    assert extrait["verified_at"] is None
    assert extrait["verified_status"] is None


@pytest.mark.asyncio
async def test_get_source_dit_la_retractation(db_session, source_complete):
    from app.mcp_server.tools import get_source

    detail = await get_source(db_session, source_id=str(source_complete.id))
    assert detail["retraction_status"] == "retracted"
    assert detail["retraction_notice_doi"] == "10.1000/avis"


@pytest.mark.asyncio
async def test_get_source_porte_position_doi_et_acces_ouvert(db_session, source_complete):
    from app.mcp_server.tools import get_source

    detail = await get_source(db_session, source_id=str(source_complete.id))
    assert detail["stance"] == "nuance-contredit"
    assert detail["doi"] == "10.1000/retiree"
    assert detail["journal"] == "Revue Exemple"
    assert detail["oa_status"] == "gold"
    assert detail["oa_url"] == "https://example.org/pdf"


@pytest.mark.asyncio
async def test_find_cards_citing_same_url(db_session, published_card, test_user):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://doi.org/10.1000/exemple")
    assert len(results) == 1
    assert results[0]["slug"] == "memoire-cerveau"
