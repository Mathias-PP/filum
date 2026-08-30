"""Objectif de session : ce que l'agent cherche à obtenir, hors de l'historique.

Sur un travail long, l'agent redérive son intention du seul historique. Or
c'est justement le début de l'historique que la compaction ampute : au bout de
quelques compactions, l'agent a oublié la demande de départ et poursuit une
version dérivée de sa propre reformulation.

Ces deux outils écrivent l'objectif et la phase courante sur la ligne de la
session, et le prompt système les réinjecte à chaque tour. Un état qui ne vit
pas dans l'historique ne peut pas être compacté avec lui.

Aucun des deux n'est sensible : poser un objectif n'écrit rien de public et se
défait en un appel. Les rendre sensibles ferait approuver sans lire là où la
confirmation compte vraiment.
"""

from __future__ import annotations

from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext
from app.services import agent_sessions

#: Les deux outils d'objectif.
#:
#: Ils touchent la base, donc ils ne partent jamais en parallèle d'un autre
#: appel : l'`AsyncSession` du contexte ne se partage pas entre coroutines. Mais
#: ils restent hors de `OUTILS_QUI_ECRIVENT`, qui sert à détecter le modèle qui
#: annonce une action jamais faite : poser un objectif ne prouve rien du travail
#: annoncé, l'y compter rendrait le contrôle aveugle au cas qu'il vise.
OUTILS_OBJECTIF: frozenset[str] = frozenset({"definir_objectif", "avancer_phase"})

_HORS_SESSION = {
    "error": "Cet outil n'est disponible que dans une conversation, il n'a pas de session à annoter."
}


async def _execute_definir_objectif(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if ctx.session_id is None:
        return _HORS_SESSION
    objectif = args.get("objectif")
    if not isinstance(objectif, str) or not objectif.strip():
        raise ValueError("definir_objectif attend un objectif (texte non vide).")
    phase = args.get("phase")
    session = await agent_sessions.fixer_objectif(
        ctx.db,
        ctx.creator_id,
        ctx.session_id,
        objectif=objectif,
        phase=phase if isinstance(phase, str) else None,
    )
    return {"objectif": session.objectif, "phase": session.phase}


async def _execute_avancer_phase(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if ctx.session_id is None:
        return _HORS_SESSION
    phase = args.get("phase")
    if not isinstance(phase, str) or not phase.strip():
        raise ValueError("avancer_phase attend une phase (texte non vide).")
    session = await agent_sessions.fixer_objectif(
        ctx.db, ctx.creator_id, ctx.session_id, phase=phase
    )
    if session.objectif is None:
        return {
            "phase": session.phase,
            "avertissement": (
                "Aucun objectif n'est posé sur cette session : appelle definir_objectif "
                "pour que la phase se rattache à quelque chose."
            ),
        }
    return {"objectif": session.objectif, "phase": session.phase}


def objectif_tools() -> list[AgentTool]:
    """Les deux outils d'objectif de session, prêts pour le registre."""
    return [
        AgentTool(
            name="definir_objectif",
            description=(
                "Enregistre en une phrase ce que cette conversation cherche à obtenir. "
                "À appeler dès que la demande du créateur est claire, avant de commencer "
                "le travail. L'objectif t'est réaffiché à chaque tour et survit à la "
                "compaction de l'historique : c'est le seul moyen de ne pas perdre "
                "l'intention de départ sur un travail long. Un nouvel appel remplace "
                "l'objectif précédent, à utiliser si le créateur change de cap."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "objectif": {
                        "type": "string",
                        "description": (
                            "Le résultat visé, en une phrase, du point de vue du créateur "
                            "(ex. « Documenter la fiche sur les mitochondries avec cinq "
                            "sources primaires vérifiées »). 400 caractères au plus."
                        ),
                    },
                    "phase": {
                        "type": "string",
                        "description": "Où en est le travail, en quelques mots (facultatif).",
                    },
                },
                "required": ["objectif"],
            },
            output="objectif, phase",
            execute=_execute_definir_objectif,
        ),
        AgentTool(
            name="avancer_phase",
            description=(
                "Met à jour où en est le travail, sans toucher à l'objectif. À appeler "
                "quand tu passes à une étape nettement différente (ex. « recherche des "
                "sources » puis « rédaction des extraits »). Ne remplace pas un compte "
                "rendu au créateur : c'est un repère pour toi, réaffiché à chaque tour."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "L'étape en cours, en quelques mots. 120 caractères au plus.",
                    }
                },
                "required": ["phase"],
            },
            output="objectif, phase",
            execute=_execute_avancer_phase,
        ),
    ]
