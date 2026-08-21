"""Outils d'orchestration de fiches exposés à l'agent.

L'agent peut *consulter* l'avancement d'un run (`fiche_state`) et connaître
la liste des étages (`fiche_etapes`). Il ne peut pas *lancer* un run depuis
une conversation : une boucle qui démarre une boucle multiplie le budget de
tours sans qu'aucune borne ne s'en aperçoive. Le lancement passe par la route
dédiée, où l'utilisateur voit ce qu'il déclenche.
"""

from __future__ import annotations

from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext

# Import différé : l'orchestrateur dépend de la boucle, qui dépend du registre,
# qui dépend de ce module. Le résoudre à l'appel plutôt qu'à l'import casse le
# cycle sans forcer aucun des trois à s'aplatir.


async def _execute_fiche_state(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.services import agent_fiche

    slug = (args.get("slug") or "").strip()
    if not slug:
        return {"error": "Le slug de la fiche est requis."}
    return await agent_fiche.etat(ctx.db, ctx.creator_id, slug)


async def _execute_fiche_etapes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.services import agent_fiche

    return {
        "etapes": [
            {"id": etape.id, "instructions": etape.instructions} for etape in agent_fiche.ETAPES
        ]
    }


def fiche_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="fiche_state",
            description="Avancement d'un run de création de fiche : étages faits, fichiers écrits.",
            parameters={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Slug de la fiche."},
                },
                "required": ["slug"],
            },
            output="dict",
            execute=_execute_fiche_state,
        ),
        AgentTool(
            name="fiche_etapes",
            description="Les étages ICM d'une création de fiche, dans l'ordre, et leurs règles.",
            parameters={"type": "object", "properties": {}, "required": []},
            output="dict",
            execute=_execute_fiche_etapes,
        ),
    ]
