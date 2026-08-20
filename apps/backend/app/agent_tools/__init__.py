"""Outils de l'agent BYOK.

Les outils sont déclaratifs (``AgentTool``) : ``name``, ``description`` (la
docstring qui oriente l'agent), ``parameters`` (schéma JSON) et ``execute``.
``ToolContext`` porte ce dont un outil a besoin : la session DB et le créateur
authentifié qui appelle. Le registre assemble les outils du workspace, de
Philum (wrappers MCP), du web et des fiches (Phase 5). La boucle d'exécution
vit dans ``app/services/agent.py``.
"""

from app.agent_tools.registry import construire_registre, executer
from app.agent_tools.tool import AgentTool, ToolContext

__all__ = ["AgentTool", "ToolContext", "construire_registre", "executer"]
