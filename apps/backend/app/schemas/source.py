from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.source import ArchiveStatus as ModelArchiveStatus


def _naive_utc(value: datetime | None) -> datetime | None:
    """Colonne `sources.published_at` = TIMESTAMP WITHOUT TIME ZONE : asyncpg
    rejette toute datetime tz-aware (DataError). Convention projet : naive UTC."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


class SourceFormat(str, Enum):
    TEXTE = "texte"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    DATA = "data"


class SourceCategory(str, Enum):
    ARTICLE_SCIENTIFIQUE = "article-scientifique"
    PREPRINT = "preprint"
    ARTICLE_PRESSE = "article-presse"
    COMMUNIQUE = "communique"
    DOCUMENTAIRE = "documentaire"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    BLOG = "blog"
    POST_SOCIAL = "post-social"
    LIVRE = "livre"
    PAGE_WEB = "page-web"
    NOTES = "notes"


class AuthorKind(str, Enum):
    CHERCHEUR = "chercheur"
    MEDIA = "media"
    INSTITUTION_PUBLIQUE = "institution-publique"
    GOUVERNEMENT = "gouvernement"
    ECOLE = "ecole"
    LABORATOIRE = "laboratoire"
    ENTREPRISE = "entreprise"
    ASSO = "asso"
    INDIVIDU = "individu"


class SourceStance(str, Enum):
    """Rapport declare entre le propos du contenu et ce que dit la source.

    Declaratif, jamais infere. `None` (non declare) n'est pas `MENTIONNE` :
    l'un est un silence, l'autre une reponse.
    """

    APPUIE = "appuie"
    NUANCE_CONTREDIT = "nuance-contredit"
    MENTIONNE = "mentionne"
    CONTEXTE = "contexte"


class RetractionStatus(str, Enum):
    """Etat de l'article aux yeux de Crossref / Retraction Watch.

    `NONE` (aucun avis, verifie) et `UNVERIFIABLE` (verification impossible)
    sont deux affirmations differentes ; les confondre reviendrait a rassurer
    le lecteur sans avoir rien verifie.
    """

    NONE = "none"
    RETRACTED = "retracted"
    CONCERN = "concern"
    CORRECTED = "corrected"
    UNVERIFIABLE = "unverifiable"


class OpenAccessStatus(str, Enum):
    """Route d'acces libre a la reference, selon OpenAlex.

    `CLOSED` (verifie, rien de gratuit) et `UNVERIFIABLE` (verification
    impossible) sont deux affirmations differentes : les confondre pourrait
    detourner le lecteur d'une version libre qui existe.
    """

    DIAMOND = "diamond"
    GOLD = "gold"
    GREEN = "green"
    HYBRID = "hybrid"
    BRONZE = "bronze"
    #: Libre par une route qu'OpenAlex nomme d'une facon inconnue ici.
    OPEN = "open"
    CLOSED = "closed"
    UNVERIFIABLE = "unverifiable"


# Reexporte depuis le modele, jamais redeclare : une copie locale avait laisse
# le schema a trois valeurs quand `not_applicable` est arrive en base, et toute
# fiche contenant une telle source repondait 500.
ArchiveStatus = ModelArchiveStatus


class SourceBase(BaseModel):
    # url peut etre vide pour les livres/chapitres/refs sans DOI ni URL
    # (DSM-IV, Enns 1998 book, Leckman 2006 chapter). L'utilisateur peut
    # completer plus tard via l'edition. La colonne DB reste NOT NULL,
    # une chaine vide satisfait la contrainte.
    url: str = Field(default="", max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    authors: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    format: SourceFormat
    category: SourceCategory
    author_kind: AuthorKind
    annotation: str | None = Field(default=None, max_length=500)
    stance: SourceStance | None = None
    is_pivot: bool = False
    parent_source_id: UUID | None = None
    # Fiche Philum que cette source designe (meta-graphe). Choisie au picker ou
    # deduite de l'URL quand elle pointe vers une fiche Philum. Doit appartenir
    # a l'utilisateur ou etre publiee — verifie cote endpoint.
    linked_card_id: UUID | None = None
    # Metadonnees bibliographiques optionnelles (exports BibTeX/CSL/APA).
    journal: str | None = Field(default=None, max_length=300)
    volume: str | None = Field(default=None, max_length=50)
    pages: str | None = Field(default=None, max_length=50)
    publisher: str | None = Field(default=None, max_length=300)
    doi: str | None = Field(default=None, max_length=200)
    # Optional manual archive URL (e.g., Wayback snapshot the user already has).
    # When provided, it is persisted as-is and the auto-archive background task
    # is skipped. Empty/null → auto-archive via Wayback "Save Page Now" runs.
    archive_url: str | None = Field(default=None, max_length=2000)

    _normalize_published_at = field_validator("published_at")(_naive_utc)


class SourceCreate(SourceBase):
    # No fields are added here. The previous `url: str` override silently
    # discarded the Field(min_length=1, max_length=2000) inherited from
    # SourceBase (Pydantic v2 replaces fields, doesn't merge). Removed
    # so input validation actually applies on the API boundary.
    pass


class SourceUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    published_at: datetime | None = None
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None
    annotation: str | None = None
    stance: SourceStance | None = None
    is_pivot: bool | None = None
    parent_source_id: UUID | None = None
    linked_card_id: UUID | None = None
    journal: str | None = Field(default=None, max_length=300)
    volume: str | None = Field(default=None, max_length=50)
    pages: str | None = Field(default=None, max_length=50)
    publisher: str | None = Field(default=None, max_length=300)
    doi: str | None = Field(default=None, max_length=200)
    archive_url: str | None = Field(default=None, max_length=2000)

    _normalize_published_at = field_validator("published_at")(_naive_utc)


class SourceExcerptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    text: str
    suggested_by_ai: bool


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    title: str | None
    authors: str | None
    published_at: datetime | None
    format: SourceFormat
    category: SourceCategory
    author_kind: AuthorKind
    annotation: str | None
    stance: SourceStance | None = None
    is_pivot: bool
    archive_status: ArchiveStatus
    archive_url: str | None
    archive_timestamp: datetime | None
    parent_source_id: UUID | None
    # Fiche Philum designee par cette source : c'est ce lien qui construit le
    # meta-graphe et la constellation.
    linked_card_id: UUID | None = None
    # Enrichi uniquement sur l'endpoint public (nombre de sources de la fiche liee).
    linked_card_sources_count: int | None = None
    conflict_of_interest: str | None = None
    # Derive de Crossref, jamais saisi : absent de SourceBase et SourceUpdate.
    # NULL = jamais verifie, ce qui ne se confond ni avec « aucun avis » ni
    # avec « non verifiable ».
    retraction_status: RetractionStatus | None = None
    retraction_notice_doi: str | None = None
    retraction_checked_at: datetime | None = None
    # Derive d'OpenAlex, jamais saisi. Meme regle a trois etats.
    oa_status: OpenAccessStatus | None = None
    oa_url: str | None = None
    oa_license: str | None = None
    # NULL = OpenAlex ne dit rien, jamais « non » par defaut.
    in_doaj: bool | None = None
    oa_checked_at: datetime | None = None
    journal: str | None = None
    volume: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    citations_count: int | None = None
    subscribers_count: int | None = None
    views_count: int | None = None
    impact_factor: float | None = None
    excerpts: list[SourceExcerptResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None


class SourceDetail(SourceResponse):
    position: int
    biblio_card_id: UUID
