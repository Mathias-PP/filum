from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.source import AuthorKind, SourceCategory, SourceFormat
from app.schemas.source import SourceResponse


class Platform(str, Enum):
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    BLOG = "blog"
    X = "x"
    BLUESKY = "bluesky"
    # Une revue scientifique n'est pas « autre » : c'est le support de
    # publication du persona chercheur, et le faire retomber dans la case
    # fourre-tout rendait `nature.com` et `sciencedirect.com` indistinguables
    # d'un site sans genre.
    REVUE_SCIENTIFIQUE = "revue-scientifique"
    OTHER = "other"


class ContentType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    POST = "post"
    PODCAST = "podcast"
    OTHER = "other"


class CardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


SlugPattern = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class CardBase(BaseModel):
    slug: str = Field(min_length=3, max_length=100, pattern=SlugPattern)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    content_url: str | None = None
    # Auteurs du contenu documente, distincts du createur de la fiche : publier
    # une fiche n'est pas signer ce qu'elle documente.
    content_authors: str | None = Field(default=None, max_length=500)
    platform: Platform = Platform.OTHER
    content_type: ContentType = ContentType.VIDEO
    visibility: Visibility = Visibility.PUBLIC


class CardCreate(CardBase):
    # Seed card = fiche cree par un utilisateur pour un contenu dont il n'est
    # PAS l'auteur (ex. mathias@... cree une fiche pour une video d'un autre
    # vulgarisateur). L'auteur reel peut la revendiquer via
    # POST /cards/{id}/claim-requests. Une seed card ne devrait pas etre
    # cryptographiquement attestee par son creator (cette regle vit dans
    # AttestationService, hors scope de ce schema).
    is_seed: bool = False
    # Meme vocabulaire que CardUpdate. Le formulaire de creation demande deja
    # ces trois champs : ne pas les accepter ici les faisait disparaitre entre
    # la saisie et la fiche, sans message, jusqu'a une edition ulterieure.
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None


class CardUpdate(BaseModel):
    #: Voir SourceUpdate : sur un schema tout-facultatif, ignorer un champ
    #: inconnu rend un corps errone indiscernable d'un corps vide.
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    content_url: str | None = None
    content_authors: str | None = Field(default=None, max_length=500)
    platform: Platform | None = None
    content_type: ContentType | None = None
    is_seed: bool | None = None
    visibility: Visibility | None = None
    # Referencement du contenu documente, meme vocabulaire que les sources.
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None


class CardStats(BaseModel):
    total_sources: int = 0
    chercheur: int = 0
    media: int = 0
    institution_publique: int = 0
    individu: int = 0
    archived_count: int = 0
    # Sources ayant une URL a archiver. Denominateur honnete du compteur :
    # `total_sources` inclut les references sans lien, qui n'ont rien a archiver.
    archivable_count: int = 0
    all_archived: bool = False


class CreatorInfo(BaseModel):
    slug: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    public_key: str


class CardSearchResult(BaseModel):
    """Fiche selectionnable comme parent (meta-fiches).

    Volontairement minimal : le picker n'a besoin que de quoi identifier une
    fiche et construire son URL publique.
    """

    id: UUID
    title: str
    slug: str
    creator_slug: str
    status: str
    # True si la fiche appartient a l'utilisateur courant : elle peut alors
    # etre un brouillon, invisible pour les autres.
    is_own: bool


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str | None
    content_url: str | None
    content_authors: str | None = None
    platform: Platform
    content_type: ContentType
    status: CardStatus
    is_seed: bool = False
    visibility: Visibility = Visibility.PUBLIC
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    # Referencement du contenu documente. NULL = non declare.
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None


class CardDetail(CardResponse):
    creator: CreatorInfo
    sources: list[SourceResponse]
    stats: CardStats


class CardPublish(BaseModel):
    status: CardStatus = CardStatus.PUBLISHED
    published_at: datetime
    public_url: str


class CardListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    status: CardStatus
    published_at: datetime | None
    total_sources: int = 0


class GraphNodeResponse(BaseModel):
    """Noeud du meta-graphe : soit une fiche, soit une de ses sources."""

    id: str
    kind: str
    depth: int
    title: str | None = None
    url: str | None = None
    authors: str | None = None
    category: str | None = None
    format: str | None = None
    author_kind: str | None = None
    stance: str | None = None
    is_pivot: bool = False
    published_at: datetime | None = None
    journal: str | None = None
    publisher: str | None = None
    doi: str | None = None
    slug: str | None = None
    creator_slug: str | None = None
    creator_name: str | None = None
    sources_count: int | None = None
    linked_card_id: UUID | None = None
    linked_card_slug: str | None = None
    linked_card_creator_slug: str | None = None
    is_seed: bool = False


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    kind: str
    # Rapport declare par la source qui porte l'arete : colore le trait.
    stance: str | None = None


class CardGraphResponse(BaseModel):
    root_id: str
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    # True si le plafond de noeuds a ete atteint : le frontend previent
    # l'utilisateur que le voisinage affiche est partiel.
    truncated: bool = False


class IncomingCitationResponse(BaseModel):
    """Une fiche publique tierce cite une fiche de l'utilisateur."""

    source_id: UUID
    cited_card_id: UUID
    cited_card_title: str
    cited_card_slug: str
    citing_card_id: UUID
    citing_card_title: str
    citing_card_slug: str
    citing_creator_slug: str
    citing_creator_name: str | None = None
    # NULL = aucun rapport declare, ce qui n'est pas « neutre ».
    stance: str | None = None
    cited_at: datetime
    is_new: bool


class IncomingCitationsResponse(BaseModel):
    citations: list[IncomingCitationResponse]
    new_count: int
    # NULL = jamais consulte. Le frontend doit le dire, pas inventer une date.
    seen_at: datetime | None = None
    truncated: bool = False
