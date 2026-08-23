"""Un extrait invente ne doit pas pouvoir entrer en base.

Ces tests portent sur la seule chose qui distingue une consigne d'une garantie :
une consigne se contourne en l'ignorant, une insertion qui echoue ne se contourne
pas. On verifie donc les trois issues possibles (`found`, `unreadable`, refus) et,
surtout, que ce qui est inscrit vient de la page et non de l'appelant.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import add_excerpt, add_source, create_card, update_excerpt
from app.services import excerpt_insertion

_PAGE = (
    "Avant le passage utile, quelques phrases de contexte editorial. "
    "La memoire n'est pas un enregistrement, c'est une reconstruction. "
    "Apres le passage utile, la page continue sur un autre sujet."
)


def _servir(monkeypatch, texte: str, *, complet: bool = True, refuse: bool = False) -> None:
    async def _page(_url: str | None) -> tuple[str, bool, bool]:
        return texte, refuse, complet

    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", _page)


@pytest.fixture
async def source_lisible(db_session, test_user, monkeypatch):
    _servir(monkeypatch, _PAGE)
    card = await create_card(db_session, test_user, slug="ancrage", title="Ancrage")
    return await add_source(
        db_session,
        test_user,
        card_slug=card["slug"],
        title="Une source lisible",
        url="https://example.org/ancrage",
    )


@pytest.mark.asyncio
async def test_un_verbatim_est_ancre(db_session, test_user, source_lisible):
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        text="La memoire n'est pas un enregistrement, c'est une reconstruction.",
    )
    assert result["verified_status"] == "found"
    assert result["text"] == "La memoire n'est pas un enregistrement, c'est une reconstruction."


@pytest.mark.asyncio
async def test_ce_qui_est_inscrit_vient_de_la_page(db_session, test_user, source_lisible):
    """Meme demande a la typographie pres : la page fait foi, pas l'appelant."""
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        # Apostrophe courbe la ou la page porte une apostrophe droite.
        text="La memoire n’est pas un enregistrement, c’est une reconstruction.",
    )
    assert result["verified_status"] == "found"
    assert "’" not in result["text"]
    assert result["text"] == "La memoire n'est pas un enregistrement, c'est une reconstruction."


@pytest.mark.asyncio
async def test_une_reformulation_est_refusee(db_session, test_user, source_lisible):
    """La source dit quelque chose de proche : le refus nomme ce qu'elle porte."""
    with pytest.raises(ToolError, match="verbatim"):
        await add_excerpt(
            db_session,
            test_user,
            source_id=source_lisible["id"],
            text="La memoire n'est pas un enregistrement fidele, mais bien une reconstruction.",
        )


@pytest.mark.asyncio
async def test_un_passage_absent_est_refuse(db_session, test_user, source_lisible):
    with pytest.raises(ToolError, match="ne figure pas dans la source"):
        await add_excerpt(
            db_session,
            test_user,
            source_id=source_lisible["id"],
            text="Les mitochondries produisent l'essentiel de l'energie cellulaire.",
        )


@pytest.mark.asyncio
async def test_page_illisible_accepte_en_unreadable(
    db_session, test_user, source_lisible, monkeypatch
):
    """Un mur anti-bot ou un PDF sans couche texte n'accuse pas la citation."""
    _servir(monkeypatch, "   ")
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        text="Un passage que la page ne rend pas, faute de rendre quoi que ce soit.",
    )
    assert result["verified_status"] == "unreadable"


@pytest.mark.asyncio
async def test_texte_partiel_ne_conclut_pas_a_l_absence(
    db_session, test_user, source_lisible, monkeypatch
):
    _servir(monkeypatch, "Un resume de la page, tronque.", complet=False)
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        text="Un passage absent du resume mais peut-etre present dans la page.",
    )
    assert result["verified_status"] == "unreadable"


@pytest.mark.asyncio
async def test_update_excerpt_reverifie_au_lieu_de_purger(db_session, test_user, source_lisible):
    ex = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        text="La memoire n'est pas un enregistrement, c'est une reconstruction.",
    )
    result = await update_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        excerpt_id=ex["id"],
        text="Avant le passage utile, quelques phrases de contexte editorial.",
    )
    assert result["verified_status"] == "found"
    assert result["text"] == "Avant le passage utile, quelques phrases de contexte editorial."


@pytest.mark.asyncio
async def test_update_excerpt_refuse_un_remplacement_invente(db_session, test_user, source_lisible):
    ex = await add_excerpt(
        db_session,
        test_user,
        source_id=source_lisible["id"],
        text="La memoire n'est pas un enregistrement, c'est une reconstruction.",
    )
    with pytest.raises(ToolError, match="ne figure pas dans la source"):
        await update_excerpt(
            db_session,
            test_user,
            source_id=source_lisible["id"],
            excerpt_id=ex["id"],
            text="La source affirme au contraire que la memoire enregistre fidelement.",
        )


def test_l_agent_ne_voit_pas_provided_text():
    """La porte de sortie humaine de `verify_excerpts` reste fermee a l'agent."""
    from app.agent_tools.philum import philum_tools

    outil = next(o for o in philum_tools() if o.name == "verify_excerpts")
    assert "provided_text" not in outil.parameters["properties"]


def _outil(nom: str):
    from app.agent_tools.philum import philum_tools

    return next(o for o in philum_tools() if o.name == nom)


@pytest.mark.asyncio
async def test_un_parametre_inconnu_est_dit_et_non_avale(db_session, test_user):
    """Filtrer en silence faisait annoncer a l'agent un extrait qui n'existait pas.

    `add_source(..., excerpt="...")` rendait un succes : le parametre inconnu
    partait a la poubelle, la source naissait nue, et le modele declarait a
    l'utilisateur un verbatim que la fiche ne portait pas.
    """
    from app.agent_tools.tool import ToolContext

    outil = _outil("add_source")
    resultat = await outil.execute(
        ToolContext(db=db_session, user=test_user, creator_id=test_user.id),
        {"card_slug": "peu-importe", "excerpt": "un verbatim"},
    )
    assert "excerpt" in resultat["error"]
    assert "Parametres acceptes" in resultat["error"]


@pytest.mark.asyncio
async def test_un_parametre_obligatoire_absent_est_nomme(db_session, test_user):
    """Sans cette garde, le modele recevait un TypeError Python brut."""
    from app.agent_tools.tool import ToolContext

    outil = _outil("add_source")
    resultat = await outil.execute(
        ToolContext(db=db_session, user=test_user, creator_id=test_user.id), {}
    )
    assert "card_slug" in resultat["error"]


def test_add_source_expose_les_extraits_inline():
    """L'aller-retour par l'identifiant de source coutait un tour a chaque source."""
    schema = _outil("add_source").parameters["properties"]
    assert schema["excerpts"]["type"] == "array"
    assert schema["excerpts"]["items"]["type"] == "object"
