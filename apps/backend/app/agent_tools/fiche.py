"""Outils d'orchestration de fiches de l'agent — socle de la Phase 5.

Phase 5 orchestrera la création de fiche automatisée (brief → source →
extraits vérifiés → synthèse) à partir du workspace. En attendant, les agents
peuvent déjà **tout construire** outil par outil ; ces outils ne font que
connaître l'existence de l'orchestration et rendent un état explicite au lieu
de faire croire à un super-pouvoir.
"""

from __future__ import annotations

from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext

_NOT_READY = "Orchestration de fiche automatisée : disponible en Phase 5 (travaux en cours)."


async def _execute_fiche_state(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {"message": _NOT_READY}


async def _execute_fiche_lancer(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {"error": _NOT_READY}


def fiche_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="fiche_state",
            description="État d'une orchestration de fiche du workspace (Phase 5).",
            parameters={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Slug de la fiche (Phase 5)."}
                },
                "required": [],
            },
            output="message",
            execute=_execute_fiche_state,
        ),
        AgentTool(
            name="fiche_lancer",
            description="Lance l'orchestration automatisée d'une fiche du workspace (Phase 5).",
            parameters={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Slug de la fiche (Phase 5)."}
                },
                "required": ["slug"],
            },
            output="message",
            execute=_execute_fiche_lancer,
        ),
    ]
