"""La couverture d'une fiche par les sous-questions de son plan."""

from __future__ import annotations

import pytest

from app.agent_tools.couverture import couverture_tools
from app.agent_tools.tool import ToolContext
from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, create_card
from app.services import embeddings, excerpt_insertion
from app.services.couverture import calculer, ecrire_plan, lire_plan

TRANSPORT = "Les emissions du transport ont baisse d'environ 11 % apres l'introduction de la taxe."
INDUSTRIE = "Les exemptions accordees a l'industrie lourde ont limite l'effet de la taxe."
PAIN = "Le prix du pain double a Paris au printemps 1789, et les emeutes se multiplient."
PAGE = f"{TRANSPORT} {INDUSTRIE} {PAIN}"

_AXES = ("transport", "industri", "financ", "lumieres")


def _vecteur(texte: str) -> list[float]:
    t = texte.lower()
    v = [1.0 if axe in t else 0.0 for axe in _AXES]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.fixture
def hors_ligne(monkeypatch):
    async def existe(url, doi):
        return None

    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)


def _sens(monkeypatch):
    async def embed(textes):
        return [_vecteur(t) for t in textes]

    monkeypatch.setattr(embeddings, "embed", embed)


async def _fiche(db_session, test_user, slug: str, extraits: list[str]) -> None:
    await create_card(db_session, test_user, slug=slug, title=slug, card_kind="sujet")
    await add_source(
        db_session,
        test_user,
        card_slug=slug,
        metadata_from="createur",
        title="Etude",
        url=f"https://exemple.test/{slug}",
        excerpts=[{"text": t, "context": "Mesure publiee"} for t in extraits],
    )


@pytest.mark.asyncio
async def test_le_plan_se_relit_sans_doublon(db_session, test_user):
    retenues = await ecrire_plan(
        db_session,
        test_user.id,
        "taxe-carbone",
        ["  Effet sur le transport ?", "Effet sur le transport ?", ""],
    )
    assert retenues == ["Effet sur le transport ?"]
    assert await lire_plan(db_session, test_user.id, "taxe-carbone") == retenues
    with pytest.raises(ValueError):
        await ecrire_plan(db_session, test_user.id, "taxe-carbone", ["   "])


@pytest.mark.asyncio
async def test_une_fiche_dont_chaque_sous_question_porte_un_extrait_est_couverte(
    db_session, test_user, hors_ligne, monkeypatch
):
    await _fiche(db_session, test_user, "taxe-carbone", [TRANSPORT, INDUSTRIE])
    await ecrire_plan(
        db_session,
        test_user.id,
        "taxe-carbone",
        ["La taxe reduit-elle les emissions du transport ?", "Quel effet sur l'industrie ?"],
    )
    _sens(monkeypatch)

    etat = await calculer(db_session, test_user.id, "taxe-carbone")

    assert etat is not None
    assert [q.extraits for q in etat.sous_questions] == [1, 1]
    assert etat.vides() == []
    assert etat.extraits == 2


@pytest.mark.asyncio
async def test_un_extrait_sans_rapport_ne_couvre_aucune_sous_question(
    db_session, test_user, hors_ligne, monkeypatch
):
    await _fiche(db_session, test_user, "revolution-1789", [PAIN])
    plan = ["Quel role de la crise financiere ?", "Quel role des idees des Lumieres ?"]
    await ecrire_plan(db_session, test_user.id, "revolution-1789", plan)
    _sens(monkeypatch)

    etat = await calculer(db_session, test_user.id, "revolution-1789")

    assert etat is not None
    assert etat.vides() == plan
    assert etat.extraits == 1


@pytest.mark.asyncio
async def test_sans_embeddings_les_mots_communs_rattachent(
    db_session, test_user, hors_ligne, monkeypatch
):
    await _fiche(db_session, test_user, "taxe-carbone", [INDUSTRIE])
    await ecrire_plan(
        db_session,
        test_user.id,
        "taxe-carbone",
        ["Quel effet des exemptions sur l'industrie lourde ?"],
    )

    async def muet(textes):
        return None

    monkeypatch.setattr(embeddings, "embed", muet)
    etat = await calculer(db_session, test_user.id, "taxe-carbone")

    assert etat is not None
    assert etat.sous_questions[0].extraits == 1


@pytest.mark.asyncio
async def test_une_source_sans_extrait_est_comptee(db_session, test_user, hors_ligne):
    await create_card(db_session, test_user, slug="nue", title="Nue", card_kind="sujet")
    await add_source(
        db_session,
        test_user,
        card_slug="nue",
        metadata_from="createur",
        title="A completer",
        url="https://exemple.test/nue",
    )
    etat = await calculer(db_session, test_user.id, "nue")
    assert etat is not None
    assert etat.sources_sans_extrait == 1
    assert etat.sous_questions == []
    assert await calculer(db_session, test_user.id, "inexistante") is None


@pytest.mark.asyncio
async def test_l_outil_pose_le_plan_d_une_fiche_du_createur_seulement(db_session, test_user):
    outil = next(o for o in couverture_tools() if o.name == "definir_plan")
    ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)

    refus = await outil.execute(ctx, {"slug": "inexistante", "sous_questions": ["Pourquoi ?"]})
    assert "error" in refus

    await create_card(
        db_session, test_user, slug="droit-de-greve", title="Grève", card_kind="sujet"
    )
    rendu = await outil.execute(
        ctx,
        {
            "slug": "droit-de-greve",
            "sous_questions": [
                "Quelle base constitutionnelle ?",
                "Quelles limites jurisprudentielles ?",
            ],
        },
    )
    assert rendu["sous_questions"] == [
        "Quelle base constitutionnelle ?",
        "Quelles limites jurisprudentielles ?",
    ]
    assert len(await lire_plan(db_session, test_user.id, "droit-de-greve")) == 2
