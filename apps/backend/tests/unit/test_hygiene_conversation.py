"""Une position se justifie, et chaque message garde son heure.

Mesures du 2026-09-13, conversations « arthrose » : neuf sources toutes
« appuie », dont une sans aucun extrait ; tous les messages d'un tour commence
a 08:57 horodates entre 09:02:14 et 09:02:24.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from fastmcp.exceptions import ToolError
from sqlalchemy import select

from app.api.v1.endpoints.agent_chat import _persister_tour
from app.db.database import async_session_maker
from app.mcp_server.tools_write import add_source, create_card, update_source
from app.models.agent_session import AgentMessage
from app.services import agent_sessions


@pytest.fixture
def _existence(monkeypatch):
    from app.mcp_server import tools_write

    async def _existe(url, doi):
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", _existe)


async def _source_sans_extrait(db_session, test_user, **extra):
    await create_card(db_session, test_user, slug="positions", title="Positions", card_kind="sujet")
    return await add_source(
        db_session,
        test_user,
        metadata_from="createur",
        card_slug="positions",
        url="https://exemple.test/position",
        title="Une source",
        **extra,
    )


@pytest.mark.asyncio
async def test_une_position_sans_extrait_est_refusee(db_session, test_user, _existence):
    source = await _source_sans_extrait(db_session, test_user)
    with pytest.raises(ToolError, match="sans extrait"):
        await update_source(db_session, test_user, source_id=source["id"], stance="appuie")


@pytest.mark.asyncio
async def test_retirer_une_position_reste_permis(db_session, test_user, _existence):
    source = await _source_sans_extrait(db_session, test_user)
    resultat = await update_source(db_session, test_user, source_id=source["id"], stance="")
    assert resultat["stance"] is None


@pytest.mark.asyncio
async def test_add_source_ne_pose_pas_une_position_sans_extrait(db_session, test_user, _existence):
    source = await _source_sans_extrait(db_session, test_user, stance="appuie")
    assert "stance_non_posee" in source


@pytest.mark.asyncio
async def test_chaque_message_du_tour_garde_son_heure(db_session, test_user):
    session = await agent_sessions.creer(db_session, test_user.id, title="Heures")
    debut = datetime(2026, 9, 13, 8, 57, 0)
    heures = [debut, debut + timedelta(minutes=2)]
    ajouts = [
        {"role": "assistant", "content": "Je cherche.", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "name": "web_search", "content": "{}"},
    ]

    await _persister_tour(test_user.id, session.id, ajouts, "Voilà.", None, heures)

    async with async_session_maker() as db:
        rangees = (
            await db.execute(
                select(AgentMessage.role, AgentMessage.created_at)
                .where(AgentMessage.session_id == UUID(str(session.id)))
                .order_by(AgentMessage.created_at)
            )
        ).all()
    assert [r for r, _ in rangees] == ["assistant", "tool", "assistant"]
    assert rangees[0][1] == debut
    assert rangees[1][1] == debut + timedelta(minutes=2)
    assert rangees[2][1] > debut + timedelta(minutes=2)
