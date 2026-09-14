"""Une synthese n'est posee que si chaque phrase renvoie a un extrait qui la soutient."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import add_source, create_card, get_my_card, poser_synthese
from app.services import embeddings, excerpt_insertion
from app.services.synthese import decouper, verifier

TRANSPORT = (
    "Les emissions du transport ont baisse d'environ 11 % apres l'introduction de la taxe carbone."
)
INDUSTRIE = "Les exemptions accordees a l'industrie lourde ont limite l'effet de la taxe carbone."
PAGE = f"{TRANSPORT} {INDUSTRIE}"
AUTRE_ID = "99999999-9999-4999-8999-999999999999"


def _axes(texte: str) -> list[float]:
    t = texte.lower()
    v = [1.0 if "transport" in t else 0.0, 1.0 if "industri" in t else 0.0]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.fixture
async def fiche(db_session, test_user, monkeypatch):
    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    excerpt_insertion.vider_le_cache()
    await create_card(
        db_session, test_user, slug="taxe-carbone", title="Taxe carbone", card_kind="sujet"
    )
    rendu = await add_source(
        db_session,
        test_user,
        card_slug="taxe-carbone",
        metadata_from="createur",
        title="Etude suedoise",
        url="https://exemple.test/taxe",
        excerpts=[
            {"text": TRANSPORT, "context": "Mesure sur le transport"},
            {"text": INDUSTRIE, "context": "Mesure sur l'industrie"},
        ],
    )

    async def embed(textes):
        return [_axes(t) for t in textes]

    monkeypatch.setattr(embeddings, "embed", embed)
    return {e["text"]: e["id"] for e in rendu["excerpts"]}


def test_chaque_phrase_garde_ses_renvois_et_les_phrases_nues_se_voient():
    a = "11111111-1111-4111-8111-111111111111"
    phrases = decouper(
        f"# Transport\nUne phrase sans renvoi. La taxe a réduit les émissions. [extrait:{a}]"
    )
    assert [(p.texte, p.renvois) for p in phrases] == [
        ("Une phrase sans renvoi.", []),
        ("La taxe a réduit les émissions.", [a]),
    ]


@pytest.mark.asyncio
async def test_une_synthese_ancree_et_soutenue_est_posee(db_session, test_user, fiche):
    texte = (
        "# Effets mesurés\n"
        f"La taxe a fait baisser les émissions du transport. [extrait:{fiche[TRANSPORT]}]\n"
        f"L'industrie lourde a été largement exemptée. [extrait:{fiche[INDUSTRIE]}]"
    )
    rendu = await poser_synthese(db_session, test_user, card_slug="taxe-carbone", text=texte)
    assert rendu["phrases"] == 2 and rendu["extraits_cites"] == 2 and rendu["soutien_verifie"]
    assert (await get_my_card(db_session, test_user, card_slug="taxe-carbone"))["synthese"] == texte


@pytest.mark.asyncio
async def test_une_phrase_sans_renvoi_fait_refuser_la_synthese(db_session, test_user, fiche):
    texte = (
        f"La taxe marche. Elle a réduit les émissions du transport. [extrait:{fiche[TRANSPORT]}]"
    )
    with pytest.raises(ToolError, match="phrase sans extrait"):
        await poser_synthese(db_session, test_user, card_slug="taxe-carbone", text=texte)


@pytest.mark.asyncio
async def test_un_renvoi_hors_fiche_est_refuse(db_session, test_user, fiche):
    _phrases, problemes, _ = await verifier(
        db_session,
        test_user.id,
        "taxe-carbone",
        f"Une affirmation du transport. [extrait:{AUTRE_ID}]",
    )
    assert any("n'est pas un extrait de cette fiche" in p.raison for p in problemes)


@pytest.mark.asyncio
async def test_une_phrase_qui_ne_dit_pas_ce_que_dit_l_extrait_est_refusee(
    db_session, test_user, fiche
):
    texte = f"L'industrie a doublé ses profits. [extrait:{fiche[TRANSPORT]}]"
    with pytest.raises(ToolError, match="ne dit pas ce que disent les extraits"):
        await poser_synthese(db_session, test_user, card_slug="taxe-carbone", text=texte)


@pytest.mark.asyncio
async def test_sans_embeddings_la_verification_reste_structurelle(
    db_session, test_user, fiche, monkeypatch
):
    async def muet(textes):
        return None

    monkeypatch.setattr(embeddings, "embed", muet)
    rendu = await poser_synthese(
        db_session,
        test_user,
        card_slug="taxe-carbone",
        text=f"L'industrie a doublé ses profits. [extrait:{fiche[TRANSPORT]}]",
    )
    assert rendu["soutien_verifie"] is False
