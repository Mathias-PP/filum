"""Avant d'ecrire la synthese, les extraits sont ranges sous la sous-question qu'ils eclairent."""

from __future__ import annotations

import pytest

from app.mcp_server.tools_write import add_source, create_card
from app.services import embeddings, excerpt_insertion
from app.services.couverture import AUTRES_EXTRAITS, ecrire_plan, extraits_par_sous_question
from app.services.deroule_guide import _bloc_extraits

TRANSPORT = "Les emissions du transport ont baisse d'environ 11 % apres l'introduction de la taxe."
INDUSTRIE = "Les exemptions accordees a l'industrie lourde ont limite l'effet de la taxe."
PAIN = "Le prix du pain double a Paris au printemps 1789, et les emeutes se multiplient."


def _axes(texte: str) -> list[float]:
    t = texte.lower()
    v = [1.0 if "transport" in t else 0.0, 1.0 if "industri" in t else 0.0]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.fixture
async def fiche(db_session, test_user, monkeypatch):
    async def page(url):
        return f"{TRANSPORT} {INDUSTRIE} {PAIN}", False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    excerpt_insertion.vider_le_cache()
    await create_card(db_session, test_user, slug="taxe", title="Taxe", card_kind="sujet")
    await add_source(
        db_session,
        test_user,
        card_slug="taxe",
        metadata_from="createur",
        title="Etude",
        url="https://exemple.test/taxe",
        excerpts=[
            {"text": TRANSPORT, "context": "Mesure"},
            {"text": INDUSTRIE, "context": "Mesure"},
            {"text": PAIN, "context": "Contexte historique"},
        ],
    )

    async def embed(textes):
        return [_axes(t) for t in textes]

    monkeypatch.setattr(embeddings, "embed", embed)
    return "taxe"


@pytest.mark.asyncio
async def test_les_extraits_sont_ranges_par_sous_question_et_le_reste_a_part(
    db_session, test_user, fiche
):
    await ecrire_plan(
        db_session,
        test_user.id,
        fiche,
        ["Effet sur le transport ?", "Effet sur l'industrie ?", "Effet sur la culture ?"],
    )
    groupes = await extraits_par_sous_question(db_session, test_user.id, fiche)

    par_question = {q: [e.texte for e in extraits] for q, extraits in groupes}
    assert par_question["Effet sur le transport ?"] == [TRANSPORT]
    assert par_question["Effet sur l'industrie ?"] == [INDUSTRIE]
    assert par_question["Effet sur la culture ?"] == []
    assert par_question[AUTRES_EXTRAITS] == [PAIN]

    bloc = _bloc_extraits(groupes)
    assert "# Effet sur le transport ?" in bloc
    assert "# Effet sur la culture ?" not in bloc
    assert "[extrait:" in bloc and "(Etude)" in bloc


@pytest.mark.asyncio
async def test_sans_plan_tous_les_extraits_forment_un_groupe(db_session, test_user, fiche):
    groupes = await extraits_par_sous_question(db_session, test_user.id, fiche)
    assert [q for q, _e in groupes] == [AUTRES_EXTRAITS]
    assert len(groupes[0][1]) == 3
    assert await extraits_par_sous_question(db_session, test_user.id, "inexistante") == []
