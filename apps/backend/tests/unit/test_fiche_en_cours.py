"""La fiche travaillee et ses identifiants sont rappeles au modele a chaque tour.

Mesure du 2026-09-13 : des identifiants de source tronques ou inventes dans une
meme conversation.
"""

from __future__ import annotations

import json

import pytest

from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, create_card
from app.services import agent as agent_svc


def _appel(nom: str, **arguments) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "function": {"name": nom, "arguments": json.dumps(arguments)}}],
    }


def test_le_slug_vient_du_dernier_appel_qui_nomme_une_fiche():
    messages = [
        _appel("create_card", slug="ancienne"),
        {"role": "tool", "content": "{}"},
        _appel("add_source", card_slug="prevention-arthrose", url="https://x.test"),
    ]
    assert agent_svc._slug_de_la_conversation(messages) == "prevention-arthrose"


def test_sans_appel_qui_nomme_une_fiche_rien():
    assert agent_svc._slug_de_la_conversation([{"role": "user", "content": "bonjour"}]) is None
    assert agent_svc._slug_de_la_conversation([_appel("web_search", query="slug")]) is None


@pytest.mark.asyncio
async def test_les_identifiants_des_sources_sont_rappeles(db_session, test_user, monkeypatch):
    async def existe(url, doi):
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    await create_card(db_session, test_user, slug="rappel", title="Rappel", card_kind="sujet")
    source = await add_source(
        db_session,
        test_user,
        metadata_from="createur",
        card_slug="rappel",
        url="https://exemple.test/rappel",
        title="Recommandations",
    )

    bloc = await agent_svc._contexte_fiche_en_cours(
        db_session, test_user.id, [_appel("get_my_card", slug="rappel")]
    )

    assert "slug : rappel" in bloc
    assert f"source_id={source['id']}" in bloc
    assert "0 extrait" in bloc


@pytest.mark.asyncio
async def test_une_fiche_d_un_autre_n_est_pas_rappelee(db_session, test_user):
    bloc = await agent_svc._contexte_fiche_en_cours(
        db_session, test_user.id, [_appel("get_my_card", slug="inexistante")]
    )
    assert bloc == ""
