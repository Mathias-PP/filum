"""Outil du plan de couverture : l'agent pose les sous-questions d'une fiche.

Sans plan, l'agent cherchait « la question » d'un bloc et s'arretait des qu'il
tenait quelques sources, sans voir les aspects qu'il n'avait pas touches. Le
plan rend ces aspects explicites ; le deroule guide s'en sert pour relancer
l'exploration sur ce qui reste vide.
"""

from __future__ import annotations

import json
from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext

#: Outils qui ecrivent dans la session : jamais en parallele.
OUTILS_COUVERTURE: frozenset[str] = frozenset({"definir_plan"})


async def _execute_definir_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # Imports differes : les services tirent la boucle, qui tire le registre.
    from fastmcp.exceptions import ToolError

    from app.mcp_server.tools_write import _fiche_du_createur
    from app.services.couverture import ecrire_plan

    slug = str(args.get("slug") or "").strip()
    brutes = args.get("sous_questions")
    if isinstance(brutes, str):
        try:
            brutes = json.loads(brutes)
        except json.JSONDecodeError:
            brutes = None
    if not isinstance(brutes, list):
        return {"error": "sous_questions attend une liste de questions."}
    try:
        await _fiche_du_createur(ctx.db, ctx.user, slug)
    except ToolError as exc:
        return {"error": str(exc)}
    try:
        retenues = await ecrire_plan(ctx.db, ctx.creator_id, slug, [str(q) for q in brutes])
    except ValueError as exc:
        return {"error": str(exc)}
    return {"slug": slug, "sous_questions": retenues}


def couverture_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="definir_plan",
            description=(
                "Pose le plan de couverture d'une fiche : les sous-questions auxquelles une "
                "réponse complète doit répondre. Une sous-question par aspect distinct de la "
                "question (par exemple causes, mécanismes, effets mesurés, limites, contexte "
                "historique ou juridique, controverses), autant que la question en appelle. "
                "Chacune est une question précise qu'une source peut éclairer. Remplace le "
                "plan précédent."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Slug de la fiche."},
                    "sous_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Les sous-questions, une par aspect.",
                    },
                },
                "required": ["slug", "sous_questions"],
            },
            output="dict",
            execute=_execute_definir_plan,
        )
    ]
