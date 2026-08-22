"""Registre des outils exposés à l'agent BYOK.

Assemble les outils des différents domaines (workspace, Philum, web, fiche)
et fournit `executer`, la seule porte d'exécution : un outil inconnu ou une
exception devient un résultat d'erreur lisible par le modèle, jamais une
crash de la boucle.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.agent_tools.fiche import fiche_tools
from app.agent_tools.philum import est_sensible, philum_tools
from app.agent_tools.tool import AgentTool, ToolContext
from app.agent_tools.web import web_tools
from app.agent_tools.workspace import workspace_tools


def construire_registre() -> dict[str, AgentTool]:
    """Tous les outils, indexés par nom."""
    outils: dict[str, AgentTool] = {}
    for outil in workspace_tools() + philum_tools() + web_tools() + fiche_tools():
        outils[outil.name] = outil
    return outils


#: Outils que le code sait produire mais qu'une configuration serveur absente
#: n'expose pas. Une definition d'agent a le droit de les citer : l'agent
#: fonctionne sans, et retrouve l'outil le jour ou la cle est posee.
NOMS_CONDITIONNELS: frozenset[str] = frozenset({"web_search"})


def noms_outils_connus(*, exposes_seulement: bool = False) -> frozenset[str]:
    """Noms d'outils acceptables dans une definition d'agent.

    Par defaut inclut les outils conditionnels ; avec ``exposes_seulement``,
    ne rend que ce que la configuration courante expose reellement.
    """
    exposes = frozenset(construire_registre())
    return exposes if exposes_seulement else exposes | NOMS_CONDITIONNELS


def filtrer(outils: dict[str, AgentTool], autorises: Iterable[str]) -> dict[str, AgentTool]:
    """Restreint le registre aux outils d'un agent, en preservant l'ordre du registre.

    Un nom autorise mais non expose (``web_search`` sans cle) est ignore
    silencieusement : c'est une absence de configuration serveur, pas une
    erreur de la definition.
    """
    permis = set(autorises)
    return {nom: outil for nom, outil in outils.items() if nom in permis}


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
    *,
    approbation_obtenue: bool = False,
) -> dict[str, Any]:
    """Exécute un outil. Une action sensible exige `approbation_obtenue`.

    La garde vit ici plutôt qu'au site d'appel : tout futur orchestrateur qui
    passera par cette porte hérite de l'approbation sans avoir à y penser, et
    l'oubli devient un refus au lieu d'une publication silencieuse.
    """
    outil = registre.get(name)
    if outil is None:
        return {"error": f"Outil inconnu : {name}."}
    if est_sensible(name, args) and not approbation_obtenue:
        return {
            "error": (
                f"L'action {name} est sensible : elle exige une validation humaine "
                "explicite et n'a pas été exécutée."
            )
        }
    try:
        return await outil.execute(ctx, args)
    except Exception as exc:  # noqa: BLE001 — l'agent lit l'erreur, la boucle continue
        return {"error": f"L'outil {name} a échoué : {exc}"}
