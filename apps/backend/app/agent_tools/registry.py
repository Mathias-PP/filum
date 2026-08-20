"""Registre des outils exposés à l'agent BYOK.

Assemble les outils des différents domaines (workspace, Philum, web, fiche)
et fournit `executer`, la seule porte d'exécution : un outil inconnu ou une
exception devient un résultat d'erreur lisible par le modèle, jamais une
crash de la boucle.
"""

from __future__ import annotations

from typing import Any

from app.agent_tools.fiche import fiche_tools
from app.agent_tools.philum import philum_tools
from app.agent_tools.tool import AgentTool, ToolContext
from app.agent_tools.web import web_tools
from app.agent_tools.workspace import workspace_tools


def construire_registre() -> dict[str, AgentTool]:
    """Tous les outils, indexés par nom."""
    outils: dict[str, AgentTool] = {}
    for outil in workspace_tools() + philum_tools() + web_tools() + fiche_tools():
        outils[outil.name] = outil
    return outils


def registre_api(outils: dict[str, AgentTool]) -> list[dict[str, Any]]:
    """Les outils au format OpenAI `tools` (function calling)."""
    return [
        {
            "type": "function",
            "function": {
                "name": outil.name,
                "description": outil.description,
                "parameters": outil.parameters,
            },
        }
        for outil in outils.values()
    ]


async def executer(
    registre: dict[str, AgentTool],
    name: str,
    args: dict[str, Any],
    ctx: ToolContext,
) -> dict[str, Any]:
    outil = registre.get(name)
    if outil is None:
        return {"error": f"Outil inconnu : {name}."}
    try:
        return await outil.execute(ctx, args)
    except Exception as exc:  # noqa: BLE001 — l'agent lit l'erreur, la boucle continue
        return {"error": f"L'outil {name} a échoué : {exc}"}
