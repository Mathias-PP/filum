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
from app.core.config import get_settings
from app.db.database import get_db
from app.models.user import User
from app.services import agent_gratuit

router = APIRouter(prefix="/agent/mode-gratuit", tags=["agent"])


def _administre_l_instance(user: User) -> bool:
    """L'utilisateur figure-t-il dans `agent_admin_emails` ?

    Le modele primaire du mode gratuit est un reglage de l'instance, partage par
    tous les comptes. Le laisser a n'importe quel utilisateur connecte, c'etait
    laisser chacun changer le modele des autres.
    """
    admins = {
        adresse.strip().lower()
        for adresse in get_settings().agent_admin_emails.split(",")
        if adresse.strip()
    }
    return user.email.lower() in admins


class ConsentementGratuit(BaseModel):
    version: str = Field(min_length=1, max_length=40)


@router.get("")
async def etat_mode_gratuit(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Disponible sur cette instance ? Actif pour cet utilisateur ?"""
    etat = await agent_gratuit.etat_consentement(db, current_user.id)
    # L'interface ne montre le choix du modele qu'a qui peut le faire : un
    # reglage offert puis refuse est pire qu'un reglage absent.
    return {**etat, "peut_choisir_modele": _administre_l_instance(current_user)}


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


class ChoixModele(BaseModel):
    model: str = Field(min_length=1, max_length=120)


@router.get("/modeles")
async def lister_modeles_gratuits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Catalogue des modeles gratuits, avec role primaire/secours de chacun."""
    return {"modeles": await agent_gratuit.liste_modeles(db)}


@router.put("/modele")
async def definir_modele_gratuit(
    body: ChoixModele,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Choisit le modele primaire du mode gratuit (toute l'instance).

    Le secours n'est pas touche : la rotation s'en sert automatiquement
    quand le primaire repond 429/surcharge. Reserve aux adresses de
    `agent_admin_emails`, puisque le choix vaut pour tous les comptes.
    """
    if not _administre_l_instance(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "reserve_administrateur",
                "message": (
                    "Le modèle gratuit sert tous les comptes : seul un administrateur "
                    "de l'instance le change."
                ),
            },
        )
    try:
        return await agent_gratuit.definir_modele_primaire(db, body.model)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": str(exc),
                "message": "Modèle inconnu du catalogue gratuit ou lane primaire absente.",
            },
        ) from exc
