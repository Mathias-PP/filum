"""`rechercher` exige de chercher ce qui contredit, reconnait les sources de la fiche et pagine."""

from __future__ import annotations

import pytest

from app.agent_tools.recherche import recherche_tools
from app.agent_tools.tool import ToolContext
from app.extractors.recherche_litterature import Candidate
from app.mcp_server.tools_write import add_source, create_card
from app.services import excerpt_insertion, recherche_approfondie
from app.services.fusion_candidates import identite
from app.services.profil_modele import PETIT_MODELE
from app.services.recherche_approfondie import REPONSE, Journal, Passage, Recherche, SourceTrouvee

PASSAGE = "Les emissions du transport ont baisse d'environ 11 % apres la taxe carbone."


def _outil(nom):
    return next(o for o in recherche_tools() if o.name == nom)


def _vide():
    return ToolContext(db=None, user=None, creator_id=None)


def _recherche(*urls: str, longueur: int = 50) -> Recherche:
    return Recherche(
        id="r1",
        sous_question="Effet sur le transport ?",
        sources=[
            SourceTrouvee(
                candidate=Candidate(url=u, titre=u, famille="web"),
                url_lue=u,
                passages=[Passage("x" * longueur, REPONSE, 0.8)],
                tour=1,
                texte_complet=True,
            )
            for u in urls
        ],
        journal=Journal(arret="saturation"),
    )


@pytest.mark.asyncio
async def test_une_recherche_sans_formulation_de_contradiction_est_refusee():
    rendu = await _outil("rechercher").execute(
        _vide(), {"sous_question": "Effet ?", "requetes": ["taxe"], "requetes_contradiction": []}
    )
    assert "requetes_contradiction" in rendu["error"]
    rendu = await _outil("rechercher").execute(
        _vide(), {"sous_question": "Effet ?", "requetes": [], "requetes_contradiction": ["x"]}
    )
    assert "requetes" in rendu["error"]


@pytest.mark.asyncio
async def test_les_resultats_se_lisent_page_par_page(monkeypatch):
    vus: dict = {}

    async def pipeline(sous_question, requetes, contradictions, **options):
        vus.update(requetes=requetes, contradictions=contradictions, **options)
        return _recherche("https://a.test/1", "https://a.test/2", longueur=4000)

    monkeypatch.setattr(recherche_approfondie, "rechercher_sous_question", pipeline)
    jeton = PETIT_MODELE.set(True)
    try:
        page1 = await _outil("rechercher").execute(
            _vide(),
            {
                "sous_question": "Effet sur le transport ?",
                "requetes": '["taxe carbone transport", "carbon tax transport"]',
                "requetes_contradiction": "limites de la taxe carbone",
            },
        )
        page2 = await _outil("suite_recherche").execute(_vide(), {"recherche_id": "r1", "page": 2})
    finally:
        PETIT_MODELE.reset(jeton)

    assert vus["requetes"] == ["taxe carbone transport", "carbon tax transport"]
    assert vus["contradictions"] == ["limites de la taxe carbone"]
    assert page1["pages"] == 2 and "suite_recherche" in page1["suite"]
    assert page1["journal"]["raison_de_l_arret"] == "saturation"
    assert [s["url"] for s in page1["sources"]] == ["https://a.test/1"]
    assert [s["url"] for s in page2["sources"]] == ["https://a.test/2"]
    assert "journal" not in page2


@pytest.mark.asyncio
async def test_ne_trouver_aucune_nuance_est_dit_sans_bloquer(monkeypatch):
    async def pipeline(sous_question, requetes, contradictions, **options):
        return _recherche("https://a.test/1")

    monkeypatch.setattr(recherche_approfondie, "rechercher_sous_question", pipeline)
    rendu = await _outil("rechercher").execute(
        _vide(),
        {"sous_question": "Effet ?", "requetes": ["taxe"], "requetes_contradiction": ["limites"]},
    )
    assert "error" not in rendu
    assert rendu["passages_qui_nuancent"] == 0
    assert "Rien ne bloque" in rendu["nuance"]
    assert len(rendu["sources"]) == 1


@pytest.mark.asyncio
async def test_une_recherche_inconnue_se_relance():
    rendu = await _outil("suite_recherche").execute(_vide(), {"recherche_id": "absente", "page": 2})
    assert "Relance rechercher" in rendu["error"]


@pytest.mark.asyncio
async def test_les_sources_deja_posees_sur_la_fiche_sont_reconnues(
    db_session, test_user, monkeypatch
):
    async def page(url):
        return PASSAGE, False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    excerpt_insertion.vider_le_cache()
    await create_card(db_session, test_user, slug="taxe", title="Taxe", card_kind="sujet")
    posee = await add_source(
        db_session,
        test_user,
        card_slug="taxe",
        metadata_from="createur",
        title="Etude",
        url="https://exemple.test/taxe",
        excerpts=[{"text": PASSAGE, "context": "Mesure"}],
    )
    vus: dict = {}

    async def pipeline(sous_question, requetes, contradictions, **options):
        vus.update(options)
        return _recherche()

    monkeypatch.setattr(recherche_approfondie, "rechercher_sous_question", pipeline)
    rendu = await _outil("rechercher").execute(
        ToolContext(db=db_session, user=test_user, creator_id=test_user.id),
        {
            "card_slug": "taxe",
            "sous_question": "Effet ?",
            "requetes": ["taxe"],
            "requetes_contradiction": ["limites"],
        },
    )
    cle = identite(Candidate(url="https://exemple.test/taxe", titre=None, famille=""))
    assert vus["deja"] == {cle: posee["id"]}
    assert rendu["sources_pertinentes"] == 0 and rendu["message"]
