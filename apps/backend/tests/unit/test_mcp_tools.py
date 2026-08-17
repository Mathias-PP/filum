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


@pytest_asyncio.fixture
async def fiche_citant_nature(db_session, test_user):
    """Une fiche qui cite un article, dans une seule des ecritures de son URL.

    Mesure en production le 2026-08-16 : `find_cards_citing` comparait l'URL
    caractere par caractere. La meme reference ecrite en `http://`, sans
    `www.`, avec une barre finale ou un parametre de campagne ne ramenait plus
    rien, alors que le reste du produit sait depuis `content_identity` que ces
    ecritures designent le meme contenu.
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="engrammes",
        title="Engrammes",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=card.id,
            position=0,
            url="https://www.nature.com/articles/nature11028",
            doi="10.1038/nature11028",
            title="Optogenetic stimulation of a hippocampal engram",
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
        )
    )
    await db_session.commit()
    return card


@pytest.mark.parametrize(
    "ecriture",
    [
        "https://www.nature.com/articles/nature11028",
        "http://www.nature.com/articles/nature11028",
        "https://nature.com/articles/nature11028",
        "https://www.nature.com/articles/nature11028/",
        "https://www.nature.com/articles/nature11028?utm_source=x",
        "https://www.nature.com/articles/nature11028#abstract",
        "  https://www.nature.com/articles/nature11028  ",
    ],
    ids=["canonique", "http", "sans-www", "barre-finale", "tracking", "fragment", "espaces"],
)
@pytest.mark.asyncio
async def test_find_cards_citing_ignore_l_ecriture_de_l_url(
    db_session, fiche_citant_nature, ecriture
):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url=ecriture)
    assert [r["slug"] for r in results] == ["engrammes"], ecriture


@pytest.mark.asyncio
async def test_find_cards_citing_reconnait_le_doi(db_session, fiche_citant_nature):
    """Un agent tient le DOI, la fiche tient l'URL de l'editeur.

    Sans cette branche, le graphe se romprait entre deux facons d'ecrire la
    meme reference que le reste du produit tient deja pour identiques.
    """
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://doi.org/10.1038/nature11028")
    assert [r["slug"] for r in results] == ["engrammes"]


@pytest.mark.asyncio
async def test_find_cards_citing_ne_confond_pas_deux_articles(db_session, fiche_citant_nature):
    from app.mcp_server.tools import find_cards_citing

    assert (
        await find_cards_citing(db_session, url="https://www.nature.com/articles/nature11029") == []
    )


@pytest.mark.asyncio
async def test_find_cards_citing_url_vide_ne_ramene_rien(db_session, fiche_citant_nature):
    """Une URL illisible ne vaut pas « toutes les fiches »."""
    from app.mcp_server.tools import find_cards_citing

    assert await find_cards_citing(db_session, url="   ") == []
    assert await find_cards_citing(db_session, url="pas une url") == []


@pytest_asyncio.fixture
async def fiche_citant_une_fiche(db_session, test_user):
    """Une fiche dont une source designe une autre fiche Philum.

    C'est l'unique arete fiche -> fiche, celle qui porte le meta-graphe. Mesure
    en production le 2026-08-17 : la fiche « Synaptic tagging during memory
    allocation » cite 103 sources, dont deux sont elles-memes documentees sur
    Philum. Le REST et la vue graphe le disent, le MCP rendait une liste plate
    ou rien ne distinguait ces deux-la.

    Retourne (fiche citante, source porteuse du lien, fiche citee).
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    citee = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-citee",
        title="Fiche citee",
        content_type="article",
        platform="web",
        status="published",
    )
    citante = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-citante",
        title="Fiche citante",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add_all([citee, citante])
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=citante.id,
        position=0,
        url="https://example.org/travail-cite",
        title="Travail cite",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
        linked_card_id=citee.id,
    )
    db_session.add(source)
    await db_session.commit()
    return citante, source, citee


@pytest.mark.asyncio
async def test_get_card_dit_qu_une_source_mene_a_une_fiche(
    db_session, fiche_citant_une_fiche, test_user
):
    from app.mcp_server.tools import get_card

    card = await get_card(db_session, creator=test_user.username, slug="fiche-citante")
    lien = card["sources"][0]["linked_card"]
    assert lien == {"creator": test_user.username, "slug": "fiche-citee"}


@pytest.mark.asyncio
async def test_get_card_ne_ment_pas_sur_une_source_sans_lien(db_session, published_card, test_user):
    """L'absence de lien se dit, pour qu'un agent sache que la question a ete posee."""
    from app.mcp_server.tools import get_card

    card = await get_card(db_session, creator=test_user.username, slug="memoire-cerveau")
    assert card["sources"][0]["linked_card"] is None


@pytest.mark.asyncio
async def test_get_source_dit_la_fiche_qu_elle_mene(db_session, fiche_citant_une_fiche):
    from app.mcp_server.tools import get_source

    _, source, _ = fiche_citant_une_fiche
    detail = await get_source(db_session, source_id=str(source.id))
    assert detail["linked_card"]["slug"] == "fiche-citee"


@pytest.mark.asyncio
async def test_le_lien_ne_revele_pas_une_fiche_non_publique(
    db_session, fiche_citant_une_fiche, test_user
):
    """Une arete est une adresse : elle ne peut pas designer ce qui est ferme.

    Le lien peut avoir ete pose quand la fiche citee etait publique. La rendre
    privee doit fermer l'arete, sinon le MCP publierait le slug d'un travail
    que son auteur a retire du monde, et l'agent y enverrait ses lecteurs.
    """
    from app.mcp_server.tools import get_card, get_source

    _, source, citee = fiche_citant_une_fiche
    citee.visibility = "private"
    await db_session.commit()

    card = await get_card(db_session, creator=test_user.username, slug="fiche-citante")
    assert card["sources"][0]["linked_card"] is None
    detail = await get_source(db_session, source_id=str(source.id))
    assert detail["linked_card"] is None


@pytest.mark.asyncio
async def test_le_lien_ne_revele_pas_un_brouillon(db_session, fiche_citant_une_fiche, test_user):
    from app.mcp_server.tools import get_card

    _, _, citee = fiche_citant_une_fiche
    citee.status = "draft"
    await db_session.commit()

    card = await get_card(db_session, creator=test_user.username, slug="fiche-citante")
    assert card["sources"][0]["linked_card"] is None


@pytest_asyncio.fixture
async def deux_ecritures_du_meme_travail(db_session, test_user):
    """Deux fiches citent le meme travail, sous deux adresses sans rien de commun.

    Mesure en production le 2026-08-17 : « ca-sert-a-quoi-de-dormir » designe
    l'article par son adresse Nature, « replay-... » par son DOI. Aucune sous-
    chaine commune, et pourtant le produit a resolu les deux vers la meme fiche.
    Demander qui cite l'article n'en rendait qu'une.
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    citee = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="article-cite",
        title="Article cite",
        content_url="https://www.nature.com/articles/nrn3667",
        content_type="article",
        platform="web",
        status="published",
    )
    db_session.add(citee)
    await db_session.flush()
    for slug, url in (
        ("par-l-adresse", "https://www.nature.com/articles/nrn3667"),
        ("par-le-doi", "https://doi.org/10.1038/nrn3667"),
    ):
        citante = BiblioCard(
            id=uuid4(),
            user_id=test_user.id,
            slug=slug,
            title=f"Fiche {slug}",
            content_type="video",
            platform="youtube",
            status="published",
        )
        db_session.add(citante)
        await db_session.flush()
        db_session.add(
            Source(
                id=uuid4(),
                biblio_card_id=citante.id,
                position=0,
                url=url,
                title="Article cite",
                format="texte",
                category="article-scientifique",
                author_kind="chercheur",
                linked_card_id=citee.id,
            )
        )
    await db_session.commit()
    return citee


@pytest.mark.asyncio
async def test_find_cards_citing_suit_le_lien_resolu(db_session, deux_ecritures_du_meme_travail):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://www.nature.com/articles/nrn3667")
    assert sorted(r["slug"] for r in results) == ["par-l-adresse", "par-le-doi"]


@pytest.mark.asyncio
async def test_find_cards_citing_ne_rend_pas_la_fiche_citee_elle_meme(
    db_session, deux_ecritures_du_meme_travail
):
    """Une fiche ne se cite pas en documentant son propre contenu."""
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://www.nature.com/articles/nrn3667")
    assert "article-cite" not in {r["slug"] for r in results}


@pytest.mark.asyncio
async def test_le_lien_resolu_ne_passe_pas_par_une_fiche_privee(
    db_session, deux_ecritures_du_meme_travail
):
    """La fiche citee devenue privee ne sert plus de pont entre deux ecritures.

    Le lien resolu reste vrai, mais il designe un travail retire du monde :
    s'en servir reviendrait a repondre a partir de ce que le public ne voit pas.
    """
    from app.mcp_server.tools import find_cards_citing

    deux_ecritures_du_meme_travail.visibility = "private"
    await db_session.commit()

    results = await find_cards_citing(db_session, url="https://www.nature.com/articles/nrn3667")
    assert [r["slug"] for r in results] == ["par-l-adresse"]
