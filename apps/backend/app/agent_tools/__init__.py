"""Registre d'outils de l'agent BYOK.

Les outils sont déclaratifs (``AgentTool``) : ``name``, ``description`` (la
docstring qui oriente l'agent), ``parameters`` (schéma JSON) et ``execute``.
``ToolContext`` porte ce dont un outil a besoin : la session DB et le créateur
qui appelle. Le registre et la boucle d'exécution vivent dans la Phase 3.
"""

from app.agent_tools.tool import AgentTool, ToolContext

__all__ = ["AgentTool", "ToolContext"]
