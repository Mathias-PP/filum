"""Endpoints du mode gratuit : état, consentement, retrait.

Le mode lui-même ne se règle PAS ici : c'est le chat qui l'utilise quand
l'utilisateur a consenti et qu'une lane est disponible. Ces endpoints
exposent seulement l'état et le consentement versionné.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services import agent_gratuit

router = APIRouter(prefix="/agent/mode-gratuit", tags=["agent"])


class ConsentementGratuit(BaseModel):
    version: str = Field(min_length=1, max_length=40)


@router.get("")
async def etat_mode_gratuit(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Disponible sur cette instance ? Actif pour cet utilisateur ?"""
    return await agent_gratuit.etat_consentement(db, current_user.id)


@router.put("")
async def donner_consentement(
    body: ConsentementGratuit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Valide le warning données (version exacte exigée) et active le mode."""
    try:
        await agent_gratuit.donner_consentement(db, current_user.id, body.version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "version_warning_inconnue",
                "message": "Version du warning inconnue : rechargez la page pour lire "
                "le texte à jour avant de consentir.",
            },
        ) from exc
    return {"actif": True, "version_warning": agent_gratuit.VERSION_WARNING}


@router.delete("")
async def retirer_consentement(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Désactive le mode : les prochains messages repartent sur la chaîne normale."""
    await agent_gratuit.retirer_consentement(db, current_user.id)
    return {"actif": False}


@router.post("/tester")
async def tester_mode_gratuit(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ping la lane qui servirait le prochain tour (diagnostic, hors quota)."""
    return await agent_gratuit.tester_lane(db)
