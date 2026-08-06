from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.models.source import LinkOrigin, SourceStance


class CardConnection(BaseModel):
    source_id: UUID
    source_title: str | None
    source_url: str
    card_id: UUID
    card_title: str
    card_slug: str
    card_creator_slug: str
    stance: SourceStance | None
    # NULL = lien anterieur a la tracabilite : on ne sait pas d'ou il vient.
    origin: LinkOrigin | None
    confirmed: bool
    editable: bool


class CardConnections(BaseModel):
    outgoing: list[CardConnection]
    incoming: list[CardConnection]
