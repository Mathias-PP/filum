"""`chercher_sources` interroge les corpus que l'arbitre designe et fusionne leurs candidates."""

from __future__ import annotations

import pytest

from app.agent_tools import litterature, web
from app.agent_tools.litterature import litterature_tools
from app.agent_tools.tool import ToolContext
from app.core.config import get_settings
from app.extractors.recherche_litterature import Candidate
from app.mcp_server import tools as lecture
from app.services.profil_modele import PETIT_MODELE


def _outil(nom):
    return next(o for o in litterature_tools() if o.name == nom)


def _article(url, famille, source, **champs):
    return Candidate(
        url=url,
        titre=champs.pop("titre", "Un article"),
        famille=famille,
        sources=[source],
        **champs,
    )


@pytest.fixture
def corpus(monkeypatch):
    """Chaque corpus rend ce que le test lui fait dire et note qu'il a ete appele."""
    appels: list[str] = []

    def simule(nom, resultat):
        async def fonction(requete, **_):
            appels.append(nom)
            return resultat

        return fonction

    monkeypatch.setattr(
        litterature,
        "chercher_openalex",
        simule(
            "litterature",
            [
                _article(
                    "https://doi.org/10.1/a", "litterature", "openalex", doi="10.1/a", citations=40
                )
            ],
        ),
    )
    monkeypatch.setattr(
        litterature,
        "chercher_europepmc",
        simule(
            "biomedical",
            [
                _article(
                    "https://doi.org/10.1/a",
                    "biomedical",
                    "europepmc",
                    doi="10.1/a",
                    acces_libre_url="https://europepmc.org/article/PMC/1",
                )
            ],
        ),
    )
    monkeypatch.setattr(litterature, "chercher_passages_s2", simule("passages", []))

    async def aucune_fiche(db, query, limit=10):
        appels.append("corpus_philum")
        return []

    monkeypatch.setattr(lecture, "search_cards", aucune_fiche)
    monkeypatch.setattr(web, "fournisseurs_web", lambda: [])
    monkeypatch.setattr(get_settings(), "semantic_scholar_api_key", "")
    return appels


@pytest.mark.asyncio
async def test_une_question_biomedicale_interroge_la_litterature_et_fusionne(corpus):
    rendu = await _outil("chercher_sources").execute(
        ToolContext(db=None, user=None, creator_id=None),
        {"requete": "Quel rôle des hormones dans l'endométriose ?"},
    )
    assert rendu["familles_interrogees"][0] == "corpus_philum"
    assert "litterature" in corpus and "biomedical" in corpus
    assert "passages" not in rendu["familles_interrogees"]
    assert len(rendu["candidates"]) == 1
    fusionnee = rendu["candidates"][0]
    assert fusionnee["sources"] == ["openalex", "europepmc"]
    assert fusionnee["citations"] == 40
    assert fusionnee["acces_libre_url"] == "https://europepmc.org/article/PMC/1"
    assert "propose_passages" in rendu["suite"]


@pytest.mark.asyncio
async def test_les_familles_demandees_sont_respectees(corpus):
    rendu = await _outil("chercher_sources").execute(
        ToolContext(db=None, user=None, creator_id=None),
        {"requete": "droit de grève", "familles": ["litterature", "inventee"]},
    )
    assert rendu["familles_interrogees"] == ["litterature"]
    assert corpus == ["litterature"]


@pytest.mark.asyncio
async def test_un_petit_modele_recoit_moins_de_candidates(corpus, monkeypatch):
    nombreuses = [
        _article(f"https://doi.org/10.1/{n}", "litterature", "openalex", doi=f"10.1/{n}")
        for n in range(30)
    ]

    async def beaucoup(requete, **_):
        return nombreuses

    monkeypatch.setattr(litterature, "chercher_openalex", beaucoup)
    jeton = PETIT_MODELE.set(True)
    try:
        rendu = await _outil("chercher_sources").execute(
            ToolContext(db=None, user=None, creator_id=None),
            {"requete": "économie", "familles": ["litterature"]},
        )
    finally:
        PETIT_MODELE.reset(jeton)
    assert 0 < len(rendu["candidates"]) < litterature.CANDIDATES_RENDUES


@pytest.mark.asyncio
async def test_references_refuse_un_sens_inconnu_et_dit_quand_rien_ne_revient(monkeypatch):
    outil = _outil("references")
    ctx = ToolContext(db=None, user=None, creator_id=None)
    assert "sens" in (await outil.execute(ctx, {"doi": "10.1/a", "sens": "voisins"}))["error"]

    async def rien(doi, **_):
        return []

    monkeypatch.setattr(litterature, "voisinage_openalex", rien)
    rendu = await outil.execute(ctx, {"doi": "10.1/a"})
    assert rendu["sens"] == "citants" and rendu["candidates"] == [] and rendu["message"]
