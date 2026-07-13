"""Serveur MCP Philum — lecture publique du graphe de fiches."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.mcp_server import tools

mcp = FastMCP(
    "philum",
    instructions=(
        "Philum expose des fiches bibliographiques publiques de createurs de contenu. "
        "Naviguer comme un graphe : search_cards pour trouver, get_card pour le detail "
        "compact d'une fiche, get_source pour une source precise, find_cards_citing "
        "pour decouvrir qui d'autre cite une URL."
    ),
)


def _session() -> AsyncSession:
    return async_session_maker()


@mcp.tool()
async def search_cards(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Recherche des fiches publiees par titre ou nom de createur (resultats compacts)."""
    async with _session() as db:
        return await tools.search_cards(db, query=query, limit=limit)


@mcp.tool()
async def get_card(creator: str, slug: str) -> dict[str, Any] | None:
    """Detail d'une fiche : description, sources compactes (id, titre, url, categorie)."""
    async with _session() as db:
        return await tools.get_card(db, creator=creator, slug=slug)


@mcp.tool()
async def get_source(source_id: str) -> dict[str, Any] | None:
    """Detail complet d'une source : auteurs, annotation, archive horodatee."""
    async with _session() as db:
        return await tools.get_source(db, source_id=source_id)


@mcp.tool()
async def find_cards_citing(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fiches publiees citant cette URL — les aretes du graphe de citations."""
    async with _session() as db:
        return await tools.find_cards_citing(db, url=url, limit=limit)


mcp_http_app = mcp.http_app(path="/")
