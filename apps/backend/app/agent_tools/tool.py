from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@dataclass(frozen=True)
class ToolContext:
    """Contexte d'exécution d'un outil.

    Porte la session DB et le créateur qui appelle : un outil n'a jamais accès
    à autre chose — un agent ne peut pas écrire hors de son propre périmètre.
    ``creator_id`` est conservé pour les outils du workspace (== ``user.id``).
    """

    db: AsyncSession
    user: User
    creator_id: UUID
    #: Session de chat en cours, quand l'outil est appelé depuis la boucle. Seuls
    #: les outils d'objectif s'en servent : le reste du catalogue est volontairement
    #: ignorant de la conversation qui l'appelle. ``None`` hors chat (tests, MCP).
    session_id: UUID | None = None


@dataclass(frozen=True)
class AgentTool:
    """Déclaration d'un outil agent (schéma dsh-like).

    ``parameters`` est un schéma JSON Schema ``object`` avec ``required``.
    ``execute`` rend toujours un ``dict`` sérialisable (jamais un objet DB) ;
    il peut lever une ``ValueError``, le registre la transforme en résultat
    d'erreur lisible par le modèle.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    output: str
    execute: Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]
