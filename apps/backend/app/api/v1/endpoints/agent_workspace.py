"""Endpoints du workspace ICM hébergé d'un créateur.

Lecture/écriture de fichiers de configuration (filesystem logique en base),
arborescence, et seed idempotent du template ICM. Toute opération est scopée
par le créateur authentifié.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.workspace_file import (
    WorkspaceFileRead,
    WorkspaceFileWrite,
    WorkspaceTreeEntry,
)
from app.services import agent_workspace

settings = get_settings()

router = APIRouter(prefix="/agent/workspace", tags=["agent-workspace"])


def _fichier_to_read(fichier) -> WorkspaceFileRead:
    return WorkspaceFileRead(
        path=fichier.path,
        sha256=fichier.sha256,
        content=fichier.content,
        created_at=fichier.created_at,
        updated_at=fichier.updated_at,
    )


@router.get("/tree", response_model=list[WorkspaceTreeEntry])
async def arbre_workspace(
    prefix: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await agent_workspace.assurer_workspace(db, current_user.id)
    return await agent_workspace.lister(db, current_user.id, prefix)


@router.get("/file", response_model=WorkspaceFileRead)
async def lire_fichier(
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        fichier = await agent_workspace.lire(db, current_user.id, path)
    except agent_workspace.WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_path", "message": str(exc)},
        ) from exc
    if fichier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Fichier introuvable."},
        )
    return _fichier_to_read(fichier)


@router.put("/file", response_model=WorkspaceFileRead)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def ecrire_fichier(
    path: str,
    request: Request,
    body: WorkspaceFileWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        fichier = await agent_workspace.ecrire(db, current_user.id, path, body.content)
    except agent_workspace.WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_path", "message": str(exc)},
        ) from exc
    return _fichier_to_read(fichier)


@router.delete("/file", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def supprimer_fichier(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await agent_workspace.supprimer(db, current_user.id, path)
    except agent_workspace.WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc
    except agent_workspace.WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_path", "message": str(exc)},
        ) from exc


@router.post("/seed")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def re_seed_workspace(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await agent_workspace.seed(db, current_user.id)
    return {"seeded": count}
