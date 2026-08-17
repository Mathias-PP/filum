"""Identifier l'utilisateur qui parle au MCP.

Le MCP en lecture est ouvert : n'importe quel agent peut lire ce que Philum
publie. L'ecriture demande de savoir *qui* ecrit, sinon une fiche naitrait
sans createur. On reutilise le meme JWT que le REST (obtenu via l'endpoint
`/auth/mcp-token`) plutot que d'inventer un mecanisme parallele : un secret
unique, une classe d'expiration unique, une seule surface a proteger.

Le token voyage dans `Authorization: Bearer ...`, forme standard reconnue par
tout client MCP.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.services.auth import ALGORITHM

settings = get_settings()


async def _user_depuis_token(db: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return None
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    return user if user and not user.deleted_at else None


def _token_dans_l_entete() -> str | None:
    try:
        request = get_http_request()
    except RuntimeError:
        # Appel hors contexte HTTP : depuis un test unitaire par exemple.
        return None
    header = request.headers.get("Authorization", "") if request else ""
    return header[7:] if header.startswith("Bearer ") else None


async def utilisateur_courant(db: AsyncSession) -> User | None:
    """L'utilisateur identifie par le Bearer, ou None si le token est absent
    ou invalide. Ne leve jamais : un tool qui accepte l'anonyme peut choisir."""
    return await _user_depuis_token(db, _token_dans_l_entete())


async def exiger_utilisateur(db: AsyncSession) -> User:
    """Meme chose, mais leve une ToolError si personne n'est identifie.

    Le message pointe l'endroit ou l'agent va chercher son token : sans cette
    indication, il verrait juste « unauthorized » et n'aurait aucune piste.
    """
    user = await utilisateur_courant(db)
    if user is None:
        raise ToolError(
            "Non authentifie. Obtenez un token via POST /api/v1/auth/mcp-token "
            "(depuis votre navigateur connecte), puis passez-le en en-tete "
            "Authorization: Bearer <token>."
        )
    return user
