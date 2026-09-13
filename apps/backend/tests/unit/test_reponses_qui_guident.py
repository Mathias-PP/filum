"""Une reponse d'outil dit quoi faire ensuite, et un resultat vide dit pourquoi.

Mesure du 2026-09-13, conversations « arthrose » : `get_card` et `get_source`
ont rendu `null` trois fois, et l'agent posait des sources sans jamais chercher
leurs passages.
"""

from __future__ import annotations

import functools

import pytest

from app.agent_tools import philum
from app.agent_tools.tool import ToolContext
from app.mcp_server import tools as lecture
from app.mcp_server import tools_write as ecriture


def _ctx() -> ToolContext:
    return ToolContext(db=None, user=None, creator_id=None, session_id=None)


def _remplacer(monkeypatch, module, nom: str, resultat):
    """Remplace un outil en gardant sa signature : le schema vu par le modele en depend."""
    original = getattr(module, nom)

    @functools.wraps(original)
    async def remplacant(*args, **kwargs):
        return resultat

    monkeypatch.setattr(module, nom, remplacant)
    return next(t for t in philum.philum_tools() if t.name == nom)


@pytest.mark.asyncio
async def test_une_fiche_introuvable_nomme_l_outil_des_brouillons(monkeypatch):
    outil = _remplacer(monkeypatch, lecture, "get_card", None)
    resultat = await outil.execute(_ctx(), {"creator": "moi", "slug": "arthrose"})
    assert "get_my_card" in resultat["error"]


@pytest.mark.asyncio
async def test_une_recherche_vide_le_dit(monkeypatch):
    outil = _remplacer(monkeypatch, lecture, "search_cards", [])
    resultat = await outil.execute(_ctx(), {"query": "arthrose"})
    assert resultat["results"] == []
    assert "list_my_cards" in resultat["message"]


@pytest.mark.asyncio
async def test_une_source_posee_annonce_la_recherche_de_passage(monkeypatch):
    outil = _remplacer(monkeypatch, ecriture, "add_source", {"id": "s1", "card_slug": "arthrose"})
    resultat = await outil.execute(
        _ctx(), {"card_slug": "arthrose", "metadata_from": "page", "url": "https://x.test"}
    )
    assert 'find_passage(source_id="s1"' in resultat["suite"]


def test_une_erreur_n_a_pas_de_suite():
    assert "suite" not in philum._guider("add_source", {"error": "refus", "id": "s1"})


def test_un_resultat_ordinaire_passe_tel_quel():
    assert philum._guider("list_sources", {"sources": []}) == {"sources": []}
