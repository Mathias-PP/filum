"""Outils filesystem du workspace ICM hébergé.

L'agent lit/écrit les fichiers de configuration du créateur (le « cerveau »
du workspace ICM) via ces outils. Les descriptions orientent le modèle vers
les règles du workspace avant d'écrire — même logique que le MCP.
"""

from __future__ import annotations

from app.agent_tools.tool import AgentTool, ToolContext
from app.services.agent_workspace import ecrire, lire, lister


def _props(**props: dict[str, object]) -> dict[str, object]:
    return {"type": "object", "properties": props, "required": list(props)}


async def _execute_lire(ctx: ToolContext, args: dict[str, object]) -> dict[str, object]:
    path = args.get("path")
    if not isinstance(path, str):
        return {"found": False, "path": path, "content": None, "sha256": None}
    fichier = await lire(ctx.db, ctx.creator_id, path)
    if fichier is None:
        return {"found": False, "path": path, "content": None, "sha256": None}
    return {
        "found": True,
        "path": fichier.path,
        "content": fichier.content,
        "sha256": fichier.sha256,
    }


async def _execute_ecrire(ctx: ToolContext, args: dict[str, object]) -> dict[str, object]:
    path = args.get("path")
    content = args.get("content")
    if not isinstance(path, str) or not isinstance(content, str):
        raise ValueError("fs_write attend path (str) et content (str).")
    fichier = await ecrire(ctx.db, ctx.creator_id, path, content)
    return {"path": fichier.path, "sha256": fichier.sha256}


async def _execute_lister(ctx: ToolContext, args: dict[str, object]) -> dict[str, object]:
    path = args.get("path")
    prefix = path if isinstance(path, str) and path else None
    entries = await lister(ctx.db, ctx.creator_id, prefix)
    return {"entries": entries}


def workspace_tools() -> list[AgentTool]:
    """Les outils du workspace ICM, prêts pour le registre de l'agent."""
    return [
        AgentTool(
            name="fs_read",
            description=(
                "Lit un fichier du workspace de configuration ICM. Avant d'écrire quoi que ce "
                "soit, lis shared/principes-editoriaux.md, shared/garde-fous.md et shared/voix-createur.md, "
                "et le CONTEXT.md de l'étage en cours (ex. stages/01-brief/CONTEXT.md)."
            ),
            parameters=_props(
                path={
                    "type": "string",
                    "description": "Chemin relatif du fichier (ex. shared/voix-createur.md).",
                }
            ),
            output="found, path, content, sha256",
            execute=_execute_lire,
        ),
        AgentTool(
            name="fs_write",
            description=(
                "Écrit un fichier du workspace de configuration ICM (crée ou remplace, jamais hors "
                "du workspace, racines fermées). Recalcule et renvoie le sha256 du contenu."
            ),
            parameters=_props(
                path={
                    "type": "string",
                    "description": "Chemin relatif du fichier (ex. runs/<slug>/00-brief.md).",
                },
                content={"type": "string", "description": "Contenu complet du fichier."},
            ),
            output="path, sha256",
            execute=_execute_ecrire,
        ),
        AgentTool(
            name="fs_list",
            description=(
                "Liste les fichiers et dossiers du workspace ICM sous un préfixe (ex. stages/, "
                "runs/<slug>/). Sans préfixe, liste la racine."
            ),
            parameters=_props(
                path={"type": "string", "description": "Préfixe de dossier (ex. stages/)."}
            ),
            output="entries: [{path, type, sha256?}]",
            execute=_execute_lister,
        ),
    ]
