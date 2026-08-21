"""Schémas du chat agent BYOK et de ses sessions.

Deux modes coexistent. Avec ``session_id``, l'historique vient de la base et
le client n'a rien à retenir. Sans, il envoie l'historique qu'il conserve, ce
qui reste utile pour un appel unitaire d'agent ou de script. ``history`` est
bornée dans les deux cas pour protéger le contexte.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=200_000)

    @field_validator("content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content ne peut pas être vide")
        return v


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=200_000)
    history: list[AgentChatMessage] = Field(default_factory=list, max_length=40)
    session_id: UUID | None = Field(
        default=None,
        description="Session à poursuivre. Absente : une session est créée et son id "
        "arrive dans l'événement `session`.",
    )

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message ne peut pas être vide")
        return v


class AgentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=200)
    provider_id: UUID | None = None


class AgentSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    provider_id: UUID | None
    created_at: datetime
    last_message_at: datetime | None


class AgentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    tool_name: str | None
    # Identifiant du tool_call auquel ce message repond : le front en a besoin
    # pour rejouer une session sans afficher deux fois chaque outil (l'appel
    # orphelin resterait « En cours… » a jamais).
    tool_call_id: str | None
    created_at: datetime


class AgentFicheRequest(BaseModel):
    """Lancement d'un run de fiche : quel contenu, sous quel slug."""

    model_config = ConfigDict(extra="forbid")

    content_url: str = Field(min_length=1, max_length=2000)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    depuis: str | None = Field(
        default=None,
        max_length=40,
        description="Reprendre à cet étage. Les comptes rendus déjà écrits servent de contexte.",
    )


class AgentApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=64)
    approved: bool


class AgentSessionUsage(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    cost_eur: float | None = None
