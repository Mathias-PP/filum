"""Outils d'interaction du déroulé guidé : demander une précision, proposer des suites.

Ils ne font rien eux-mêmes. Le déroulé lit leurs arguments et agit : il pose
la question au créateur et attend sa réponse (Open Deep Research
`clarify_with_user`, question à choix de Morphic), ou affiche les suites sous
le bilan (questions liées de Perplexity, suggestions de Vane). Le modèle garde
ce qui demande de comprendre la question ; le serveur tient l'interaction.
"""

from __future__ import annotations

from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext


def _liste(valeur: Any) -> list[str]:
    if not isinstance(valeur, list):
        return []
    return [" ".join(str(v).split()) for v in valeur if str(v).strip()]


async def _execute_demander_precision(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    question = " ".join(str(args.get("question") or "").split())
    options = _liste(args.get("options"))
    if not question or len(options) < 2:
        return {
            "error": (
                "demander_precision attend question (str) et au moins deux options : "
                "une précision se choisit entre des angles distincts."
            )
        }
    return {"posee": True, "message": "La question part au créateur. Termine l'étape."}


async def _execute_proposer_suites(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    questions = _liste(args.get("questions"))
    if not questions:
        return {"error": "proposer_suites attend questions : au moins une sous-question."}
    return {"proposees": len(questions)}


def deroule_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="demander_precision",
            description=(
                "Pose au créateur une question à choix quand la demande admet des angles très "
                "différents qui donneraient des fiches différentes. Ne l'appelle pas pour une "
                "question claire."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "La question au créateur."},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Les angles possibles, chacun en une phrase courte.",
                    },
                },
                "required": ["question", "options"],
            },
            output="posee",
            execute=_execute_demander_precision,
        ),
        AgentTool(
            name="proposer_suites",
            description=(
                "Propose au créateur des sous-questions que la fiche ne couvre pas encore et "
                "qui la prolongeraient. Elles s'affichent sous la réponse, à lancer en un clic."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Des sous-questions précises, chacune qu'une source peut éclairer.",
                    }
                },
                "required": ["questions"],
            },
            output="proposees",
            execute=_execute_proposer_suites,
        ),
    ]
