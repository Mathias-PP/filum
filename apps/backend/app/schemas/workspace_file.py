from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_CONTENT_MAX = 1_000_000


class WorkspaceFileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=_CONTENT_MAX)


class WorkspaceFileRead(BaseModel):
    path: str
    sha256: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceSyncEntry(BaseModel):
    path: str
    #: `absent` le template le connait, le workspace ne l'a pas. `a_jour`
    #: identiques. `obsolete` le template a avance et le fichier est reste ce
    #: que le seed avait pose, donc actualisable sans rien perdre. `diverge` le
    #: fichier a pu etre edite ici : jamais ecrase sans demande explicite.
    etat: Literal["absent", "a_jour", "obsolete", "diverge"]


class WorkspaceSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Chemins divergents a reprendre du template malgre tout. Vide par defaut :
    #: une adoption ecrase une edition, elle se demande chemin par chemin.
    adopt: list[str] = Field(default_factory=list)


class WorkspaceSyncResult(BaseModel):
    ajoutes: list[str]
    mis_a_jour: list[str]
    adoptes: list[str]
    #: Laisses intacts, faute d'avoir ete demandes dans `adopt`.
    divergents: list[str]


class WorkspaceTreeEntry(BaseModel):
    path: str
    type: Literal["file", "directory"]
    sha256: str | None = None
    updated_at: datetime | None = None
    #: Layer ICM du fichier : L0 routing racine, L1 routing pipeline, L2
    #: contrat de stage, L3 factory (reference stable). None pour un dossier
    #: ou un fichier utilisateur hors des racines conventionnelles.
    layer: str | None = None
    #: Phrase de contrat : ce que ce fichier fait. Extrait du frontmatter YAML
    #: `contract:`, ou a defaut du premier paragraphe du fichier tronque.
    #: None pour un dossier.
    contract: str | None = None
