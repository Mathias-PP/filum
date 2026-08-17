"""Serveur MCP Philum — lecture publique du graphe de fiches."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.mcp_server import tools
from app.mcp_server.auth import utilisateur_courant

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
    """Cherche des fiches publiees par sujet, par createur, ou par un travail cite.

    Le terme est confronte au titre et a la description de la fiche, a l'auteur
    du contenu, au createur, et au titre comme aux auteurs des sources citees.
    Chercher le nom d'un chercheur ou le titre d'un article ramene donc les
    fiches qui s'y appuient. Accents indifferents. Resultats compacts :
    enchainer sur get_card pour le detail.
    """
    async with _session() as db:
        return await tools.search_cards(db, query=query, limit=limit)


@mcp.tool()
async def get_card(creator: str, slug: str) -> dict[str, Any] | None:
    """Detail d'une fiche : description et sources compactes.

    Chaque source porte `linked_card` : l'adresse `{creator, slug}` de la fiche
    Philum qui documente ce travail cite, ou `null`. C'est l'arete de fiche a
    fiche, a suivre par get_card pour lire ses extraits verifies.
    """
    async with _session() as db:
        return await tools.get_card(db, creator=creator, slug=slug)


@mcp.tool()
async def get_source(source_id: str) -> dict[str, Any] | None:
    """Detail complet d'une source : extraits verbatim, retractation, archive horodatee.

    Porte aussi `linked_card`, la fiche Philum qui documente ce travail cite,
    ou `null`.
    """
    async with _session() as db:
        return await tools.get_source(db, source_id=source_id)


@mcp.tool()
async def find_cards_citing(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fiches publiees citant cette reference : les aretes du graphe de citations.

    L'ecriture de l'URL est indifferente (schema, `www.`, barre finale,
    parametres de campagne). Un DOI est reconnu comme l'URL de l'editeur, et
    reciproquement : passer `https://doi.org/10.1038/nature11028` ramene les
    fiches qui citent l'article sous son adresse Nature.
    """
    async with _session() as db:
        return await tools.find_cards_citing(db, url=url, limit=limit)


@mcp.tool()
async def whoami() -> dict[str, Any] | None:
    """L'utilisateur identifie par le token, ou `null` si personne.

    A appeler en premier apres avoir configure son token : verifie que
    l'authentification passe avant de tenter une action d'ecriture.
    """
    async with _session() as db:
        user = await utilisateur_courant(db)
        if user is None:
            return None
        return {"creator": user.username, "display_name": user.display_name}


mcp_http_app = mcp.http_app(path="/")
