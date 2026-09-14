"""L'outil MCP de transcription YouTube s'execute.

Constate le 2026-09-14 en production : l'outil importait un module qui n'a
jamais existe, et chaque appel levait ModuleNotFoundError.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.extractors import youtube_oracle
from app.mcp_server.tools_write import get_youtube_transcript

VIDEO = "https://www.youtube.com/watch?v=x0g3571mS_M"


@pytest.mark.asyncio
async def test_la_transcription_est_rendue(db_session, test_user, monkeypatch):
    async def transcription(url):
        return "Bonjour, aujourd'hui on parle d'endometriose."

    monkeypatch.setattr(youtube_oracle, "fetch_youtube_transcript", transcription)
    rendu = await get_youtube_transcript(db_session, test_user, url=VIDEO)
    assert rendu == {"url": VIDEO, "transcript": "Bonjour, aujourd'hui on parle d'endometriose."}


@pytest.mark.asyncio
async def test_sans_transcription_le_refus_est_lisible(db_session, test_user, monkeypatch):
    async def rien(url):
        return None

    monkeypatch.setattr(youtube_oracle, "fetch_youtube_transcript", rien)
    with pytest.raises(ToolError, match="Aucun transcript"):
        await get_youtube_transcript(db_session, test_user, url=VIDEO)
