"""Schemas de lecture des agents nommes.

Un agent est un fichier du workspace ; il n'y a donc pas de schema de
creation ou de mise a jour ici. Ecrire un agent, c'est ecrire son fichier
via `PUT /agent/workspace/file`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    contract: str
    system_prompt: str
    tools: list[str]
    context: list[str]
    layer: str | None
    model_hint: str | None
    #: Livre avec Philum : « Restaurer template » le recree s'il est supprime.
    builtin: bool
    #: Outils demandes que la configuration serveur n'expose pas aujourd'hui.
    tools_absents: list[str]
    #: Chemin du fichier qui porte cette definition, pour ouvrir l'editeur.
    path: str


class AgentDefinitionRejected(BaseModel):
    """Un fichier de `agents/` qui ne decrit pas un agent exploitable."""

    path: str
    raison: str


class AgentDefinitionList(BaseModel):
    agents: list[AgentDefinitionRead]
    #: Rendus au client pour que le createur voie ses fichiers casses au lieu
    #: de constater une disparition silencieuse dans le selecteur.
    rejected: list[AgentDefinitionRejected]
