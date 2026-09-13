"""Un petit modele recoit un contexte a sa taille.

Mesure du 2026-09-13 : environ 70 000 caracteres d'instructions et de schemas
avant la question pour l'assistant par defaut, 16 789 jetons au premier appel,
et 79 extraits refuses sur 83 avec un modele de 8 milliards de parametres.
"""

from __future__ import annotations

import json
from hashlib import sha256

import httpx
import pytest

from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.models.workspace_file import WorkspaceFile
from app.services import agent as agent_svc
from app.services.profil_modele import (
    ESSENTIEL,
    chemins_de_contexte,
    description_courte,
    est_petit_modele,
)


@pytest.mark.parametrize(
    "modele",
    [
        "ministral-8b-latest",
        "ministral-3b-2410",
        "llama-3.1-8b-instant",
        "glm-4.7-flash",
        "qwen2.5-14b",
    ],
)
def test_les_petits_modeles_sont_reconnus(modele):
    assert est_petit_modele(modele)


@pytest.mark.parametrize(
    "modele",
    [
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
        "gemini-2.5-flash",
        "llama-3.3-70b-versatile",
        "claude-sonnet-5",
        "",
        None,
    ],
)
def test_les_autres_restent_grands(modele):
    assert not est_petit_modele(modele)


def test_l_essentiel_tient_en_quelques_lignes():
    assert len(ESSENTIEL) < 2000
    assert "find_passage" in ESSENTIEL


def test_la_description_courte_est_la_premiere_phrase():
    assert (
        description_courte("Ajoute une source. Longue suite\n de details.") == "Ajoute une source."
    )


def test_un_petit_modele_garde_les_fichiers_de_son_etape_et_perd_shared():
    chemins = ["shared/garde-fous.md", "stages/04-extraits/CONTEXT.md"]
    assert chemins_de_contexte(chemins, True) == ["stages/04-extraits/CONTEXT.md"]
    assert chemins_de_contexte(None, True) == []
    assert chemins_de_contexte(chemins, False) == chemins
    assert chemins_de_contexte(None, False) is None


async def _prompt_envoye(db_session, test_user, modele: str) -> dict:
    contenu = "Principe editorial de test."
    db_session.add(
        WorkspaceFile(
            creator_id=test_user.id,
            path="shared/principes.md",
            content=contenu,
            sha256=sha256(contenu.encode()).hexdigest(),
        )
    )
    cle = KeyManager(get_settings().master_encryption_key).encrypt_private_key("sk-test-12345678")
    provider = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url="https://api.openai.com",
        model=modele,
        api_key_enc=cle,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.commit()
    corps: list[dict] = []

    def handler(request):
        corps.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}], "usage": {}},
        )

    async def emit(event):
        return None

    async def refuse(request_id, tool, args):
        return False

    await agent_svc.boucle(
        db_session,
        test_user,
        provider,
        [{"role": "user", "content": "test"}],
        emit,
        refuse,
        transport=httpx.MockTransport(handler),
    )
    return corps[0]


@pytest.mark.asyncio
async def test_un_petit_modele_recoit_l_essentiel_et_des_outils_courts(db_session, test_user):
    corps = await _prompt_envoye(db_session, test_user, "ministral-8b-latest")
    systeme = next(m for m in corps["messages"] if m["role"] == "system")["content"]
    assert "Règles essentielles" in systeme
    assert "Principe editorial de test." not in systeme
    add_source = next(t for t in corps["tools"] if t["function"]["name"] == "add_source")
    assert len(add_source["function"]["description"]) < 300


@pytest.mark.asyncio
async def test_un_grand_modele_garde_tout_le_contexte(db_session, test_user):
    corps = await _prompt_envoye(db_session, test_user, "gpt-4o")
    systeme = next(m for m in corps["messages"] if m["role"] == "system")["content"]
    assert "Règles essentielles" not in systeme
    assert "Principe editorial de test." in systeme


def _ctx():
    from app.agent_tools.tool import ToolContext

    return ToolContext(db=None, user=None, creator_id=None, session_id=None)


@pytest.mark.asyncio
async def test_un_petit_modele_lit_une_page_par_fenetres(monkeypatch):
    from app.agent_tools import web
    from app.services import excerpt_insertion
    from app.services.profil_modele import FENETRE_LECTURE_PETIT, PETIT_MODELE

    page = "a" * (FENETRE_LECTURE_PETIT * 2 + 10)

    async def texte(url):
        return page, False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", texte)
    monkeypatch.setattr(web, "assert_url_is_safe", lambda url: None)
    jeton = PETIT_MODELE.set(True)
    try:
        premiere = await web._execute_fetch_url(_ctx(), {"url": "https://exemple.test/p"})
        derniere = await web._execute_fetch_url(
            _ctx(), {"url": "https://exemple.test/p", "page": 9}
        )
    finally:
        PETIT_MODELE.reset(jeton)

    assert len(premiere["text"]) == FENETRE_LECTURE_PETIT
    assert premiere["pages"] == 3
    assert "page=2" in premiere["suite"]
    assert derniere["page"] == 3
    assert len(derniere["text"]) == 10
    assert "suite" not in derniere


@pytest.mark.asyncio
async def test_un_petit_modele_recoit_moins_de_resultats_de_recherche(monkeypatch):
    from app.agent_tools import web
    from app.services.profil_modele import (
        EXTRAIT_RECHERCHE_PETIT,
        PETIT_MODELE,
        RESULTATS_RECHERCHE_PETIT,
    )

    async def rechercher(provider, cle, query):
        return [
            {"url": f"https://r{i}.test", "title": "t", "snippet": "x" * 1000} for i in range(8)
        ]

    monkeypatch.setattr(web, "_rechercher", rechercher)
    monkeypatch.setattr(web.settings, "agent_web_search_provider", "tavily")
    monkeypatch.setattr(web.settings, "agent_web_search_api_key", "cle")
    jeton = PETIT_MODELE.set(True)
    try:
        petit = await web._execute_web_search(_ctx(), {"query": "arthrose"})
    finally:
        PETIT_MODELE.reset(jeton)
    grand = await web._execute_web_search(_ctx(), {"query": "arthrose"})

    assert len(petit["results"]) == RESULTATS_RECHERCHE_PETIT
    assert len(petit["results"][0]["snippet"]) == EXTRAIT_RECHERCHE_PETIT
    assert len(grand["results"]) == 8
