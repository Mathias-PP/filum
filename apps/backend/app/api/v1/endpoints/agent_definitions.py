"""Endpoints de lecture des agents nommes du createur.

Il n'y a volontairement ni POST ni PATCH ni DELETE : un agent est un fichier
`agents/<slug>.yaml` du workspace. Le creer, l'editer ou le supprimer passe
par les endpoints de workspace deja en place, ce qui evite deux chemins
d'ecriture pour un meme objet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.agent_definition import (
    AgentDefinitionList,
    AgentDefinitionRead,
    AgentDefinitionRejected,
)
from app.services import agent_definitions, agent_workspace

router = APIRouter(prefix="/agent/definitions", tags=["agent-definitions"])


def _to_read(definition: agent_definitions.AgentDefinition) -> AgentDefinitionRead:
    return AgentDefinitionRead(
        slug=definition.slug,
        name=definition.name,
        contract=definition.contract,
        system_prompt=definition.system_prompt,
        tools=list(definition.tools),
        context=list(definition.context),
        layer=definition.layer,
        model_hint=definition.model_hint,
        builtin=definition.builtin,
        tools_absents=list(definition.tools_absents),
        path=agent_definitions.chemin_de(definition.slug),
    )


@router.get("", response_model=AgentDefinitionList)
async def lister_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await agent_workspace.assurer_workspace(db, current_user.id)
    valides, rejetes = await agent_definitions.lister(db, current_user.id)
    return AgentDefinitionList(
        agents=[_to_read(d) for d in valides],
        rejected=[AgentDefinitionRejected(path=r.path, raison=r.raison) for r in rejetes],
    )


@router.get("/{slug}", response_model=AgentDefinitionRead)
async def obtenir_agent(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    definition = await agent_definitions.obtenir(db, current_user.id, slug)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": f"Aucun agent « {slug} »."},
        )
    return _to_read(definition)
