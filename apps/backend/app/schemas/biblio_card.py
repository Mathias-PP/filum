from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.biblio_card import CardKind
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


#: Longueur pratique du texte integral du contenu. 500 000 caracteres = un
#: roman entier ; au-dela, ce n'est plus un contenu, c'est un corpus, qui a sa
#: propre voie (une fiche par chapitre / episode / article).
_MAX_CONTENT_TEXT = 500_000


#: Champs qui decrivent le contenu documente. Une fiche sujet n'en documente
#: aucun : les porter reviendrait a inventer un contenu qui n'existe pas.
CHAMPS_DU_CONTENU = ("content_url", "content_authors", "content_text", "platform", "content_type")


def _refuser_champs_de_contenu(valeurs: dict) -> None:
    """Leve si une fiche sujet porte un champ reserve aux fiches contenu."""
    portes = [c for c in CHAMPS_DU_CONTENU if valeurs.get(c) not in (None, "")]
    if portes:
        raise ValueError(
            "Une fiche sujet ne documente aucun contenu existant : "
            f"{', '.join(portes)} n'a pas de sens ici. Une bibliographie sur une "
            "question porte son titre, sa description et ses sources. Pour "
            "documenter une video ou un article precis, utilisez card_kind="
            "'contenu'."
        )


class CardBase(BaseModel):
    slug: str = Field(min_length=3, max_length=100, pattern=SlugPattern)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    #: Ce que la fiche documente. Voir `app.models.biblio_card.CardKind`.
    card_kind: CardKind = CardKind.CONTENU
    content_url: str | None = None
    #: Texte integral du contenu documente. L'utilisateur declare avoir le
    #: droit de le publier (contenu propre, libre de droit, ou droit de
    #: citation) : l'UI l'en avertit, le backend fait confiance.
    content_text: str | None = Field(default=None, max_length=_MAX_CONTENT_TEXT)
    # Auteurs du contenu documente, distincts du createur de la fiche : publier
    # une fiche n'est pas signer ce qu'elle documente.
    content_authors: str | None = Field(default=None, max_length=500)
    #: NULL sur une fiche sujet : elle ne documente aucun contenu, donc il n'y
    #: a ni plateforme ni type a declarer. `other` aurait garde la meme
    #: confusion sous un autre nom.
    platform: Platform | None = None
    content_type: ContentType | None = None
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

    @model_validator(mode="after")
    def _coherence_de_la_nature(self) -> CardCreate:
        if self.card_kind is CardKind.SUJET:
            _refuser_champs_de_contenu({c: getattr(self, c) for c in CHAMPS_DU_CONTENU})
            if self.is_seed:
                raise ValueError(
                    "Une fiche sujet est ecrite par son createur : il n'y a pas "
                    "d'auteur tiers a qui la reclamer, donc is_seed n'a pas de sens. "
                    "is_seed ne vaut que pour une fiche contenu creee au nom de "
                    "l'auteur du contenu documente."
                )
            return self

        # L'URL du contenu n'est pas exigee ici : une fiche nait brouillon, et
        # un brouillon est par definition inacheve. C'est la publication qui
        # l'exige, parce que c'est elle qui transforme la fiche en affirmation
        # publique « je documente ce contenu ».
        #
        # `other` est la case honnete d'un contenu dont la plateforme ou le
        # genre ne figure pas dans la liste. Le defaut historique `video`
        # affirmait, lui, quelque chose que personne n'avait declare.
        if self.platform is None:
            self.platform = Platform.OTHER
        if self.content_type is None:
            self.content_type = ContentType.OTHER
        return self


class CardUpdate(BaseModel):
    #: Voir SourceUpdate : sur un schema tout-facultatif, ignorer un champ
    #: inconnu rend un corps errone indiscernable d'un corps vide.
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    #: Changer la nature d'une fiche est possible, mais la coherence avec ce
    #: qui est deja stocke ne se juge qu'en connaissant la fiche : la regle
    #: croisee vit dans l'endpoint, pas ici.
    card_kind: CardKind | None = None
    content_url: str | None = None
    #: Voir CardBase.content_text. Chaine vide autorisee : elle efface le
    #: texte precedemment stocke, ce qui est l'operation utile face a un
    #: warning « ce texte est publie publiquement, l'effacer maintenant ».
    content_text: str | None = Field(default=None, max_length=_MAX_CONTENT_TEXT)
    content_authors: str | None = Field(default=None, max_length=500)
    platform: Platform | None = None
    content_type: ContentType | None = None
    is_seed: bool | None = None
    visibility: Visibility | None = None
    # Referencement du contenu documente, meme vocabulaire que les sources.
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None

    @model_validator(mode="after")
    def _coherence_de_la_nature(self) -> CardUpdate:
        if self.card_kind is CardKind.SUJET:
            _refuser_champs_de_contenu({c: getattr(self, c) for c in CHAMPS_DU_CONTENU})
            if self.is_seed:
                raise ValueError(
                    "Une fiche sujet est ecrite par son createur : il n'y a pas "
                    "d'auteur tiers a qui la reclamer, donc is_seed n'a pas de sens."
                )
        return self


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
    #: Ce que la fiche documente. Le frontend s'en sert pour n'afficher que ce
    #: qui a un sens : pas de bloc « contenu documente » sur une fiche sujet.
    card_kind: CardKind = CardKind.CONTENU
    content_url: str | None
    content_text: str | None = None
    content_authors: str | None = None
    platform: Platform | None = None
    content_type: ContentType | None = None
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
