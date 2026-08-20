"""Schémas du chat agent BYOK (Phase 3 : appel unitaire sans session).

La session (persistance des messages, reprise, approbation différée) arrive en
Phase 4 : aujourd'hui le client envoie l'historique qu'il veut conserver et
reçoit un flux SSE. ``history`` est bornée pour protéger le contexte.
"""

from __future__ import annotations

from typing import Literal

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

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message ne peut pas être vide")
        return v
