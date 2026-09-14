from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.champs_bibliographiques import auteurs_bibliographiques, titre_bibliographique
from app.core.nature_source import nature_corrigee
from app.db.database import Base

if TYPE_CHECKING:
    from app.models.biblio_card import BiblioCard
    from app.models.source_excerpt import SourceExcerpt


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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

    Declaratif, jamais infere : c'est l'auteur de la fiche qui l'affirme et en
    repond. NULL reste la valeur normale -- une bibliographie non annotee vaut
    mieux qu'une bibliographie annotee au hasard.
    """

    APPUIE = "appuie"
    NUANCE_CONTREDIT = "nuance-contredit"
    MENTIONNE = "mentionne"
    CONTEXTE = "contexte"


class LinkOrigin(str, Enum):
    """D'ou vient le lien d'une source vers une fiche Philum.

    MANUEL et URL sont des gestes du createur : ils valent confirmation.
    CONTENU est une hypothese de la machine (meme DOI, meme URL normalisee) :
    elle vaut proposition, pas declaration. Les confondre ferait porter au
    createur une affirmation qu'il n'a pas faite.
    """

    MANUEL = "manuel"
    URL = "url"
    CONTENU = "contenu"


class MetadataOrigin(str, Enum):
    """Qui fait foi pour le titre, les auteurs, la date, la revue, l'editeur.

    L'agent choisit l'origine, il ne saisit plus les valeurs : c'est la seule
    forme qui rende l'invention impossible plutot que deconseillee. Ce que
    l'origine choisie ne rend pas reste vide, et le vide est un etat affichable.

    CREATEUR est la porte de sortie legitime, quand le createur dicte ce qu'il
    a sous les yeux et qu'aucun resolveur ne connait la source. Elle demande une
    approbation nommee, pour qu'un agent ne puisse pas s'y rabattre en silence.

    NULL en base se lit « origine inconnue » : la source a ete posee avant que
    la regle existe. Ne jamais retro-remplir, ce serait affirmer une origine
    qu'on ignore.
    """

    PAGE = "page"
    CROSSREF = "crossref"
    OPENALEX = "openalex"
    CREATEUR = "createur"


class ArchiveStatus(str, Enum):
    PENDING = "pending"
    ARCHIVED = "archived"
    FAILED = "failed"
    # Rien a archiver : la reference n'a pas d'URL (un manuel, un chapitre de
    # livre, un entretien non publie). Distinct de FAILED, qui affirme qu'on a
    # essaye et que la page est perdue -- une affirmation invendable ici, et
    # qui condamnait le compteur « Archivees » a ne jamais etre complet.
    NOT_APPLICABLE = "not_applicable"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    biblio_card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("biblio_cards.id"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url: Mapped[str] = mapped_column(String(2000), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    author_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    annotation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rapport declare au propos (cf. SourceStance). NULL = non declare, ce qui
    # se distingue de « mentionne » : l'un est un silence, l'autre une reponse.
    stance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_pivot: Mapped[bool] = mapped_column(default=False)
    archive_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    archive_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    archive_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Quand on a *essaye* -- a ne pas confondre avec `archive_timestamp`, qui
    # date la capture. Sert a servir en premier les sources tentees le moins
    # recemment : sans cela, la queue d'un lot budgete n'est jamais atteinte.
    archive_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parent_source_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=True,
        index=True,
    )
    # Fiche Philum que cette source designe. Choisie explicitement au picker,
    # ou deduite quand l'URL matche /@{username}/{slug} sur notre frontend.
    # C'est l'unique lien fiche -> fiche : il porte le meta-graphe.
    linked_card_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("biblio_cards.id"),
        nullable=True,
        index=True,
    )
    # Provenance du lien fiche a fiche. NULL = anterieur a la tracabilite.
    link_origin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    link_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conflict_of_interest: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Avis de retractation (cf. extractors/retraction.py). Trois etats a ne pas
    # confondre : NULL = jamais verifie, "unverifiable" = verification impossible,
    # "none" = Crossref connait le DOI et ne signale rien. La date rend la
    # troisieme affirmation datable, donc honnete.
    retraction_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retraction_notice_doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retraction_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Motif de l'avis, dans le vocabulaire de Retraction Watch et verbatim (cf.
    # extractors/retraction_watch.py). Crossref ne le donne pas : il n'arrive
    # que par la passe de `app.scripts.motifs_retractation`, et reste donc NULL
    # sur une source pourtant retractee tant que cette passe n'a pas tourne.
    # NULL se lit « motif inconnu ici », jamais « avis sans motif » : ce
    # dernier existe et se dit, Retraction Watch l'ecrit « Notice - Limited or
    # No Information ».
    retraction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Acces libre (cf. extractors/open_access.py). Meme regle a trois etats :
    # NULL = jamais verifie, "unverifiable" = verification impossible,
    # "closed" = OpenAlex connait la reference et ne trouve rien de gratuit.
    oa_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    oa_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    oa_license: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # NULL = OpenAlex ne dit rien. False affirmerait que la revue n'est pas
    # referencee au DOAJ, ce que personne n'a verifie.
    in_doaj: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    oa_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Metadonnees bibliographiques optionnelles (exports BibTeX/CSL/APA).
    journal: Mapped[str | None] = mapped_column(String(300), nullable=True)
    volume: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(300), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Qui a fait foi pour les metadonnees ci-dessus (cf. MetadataOrigin). NULL
    # sur les lignes posees avant la regle : origine inconnue, pas origine
    # absente.
    metadata_origin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    citations_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscribers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impact_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Soft-delete: a non-null value hides the row from all standard queries.
    # See migration 008_source_deleted_at + the matching .deleted_at columns
    # already present on User (TimestampMixin) and BiblioCard.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    biblio_card: Mapped[BiblioCard] = relationship(
        "BiblioCard",
        back_populates="sources",
        foreign_keys=[biblio_card_id],
    )
    linked_card: Mapped[BiblioCard | None] = relationship(
        "BiblioCard",
        foreign_keys=[linked_card_id],
    )
    parent: Mapped[Source | None] = relationship(
        "Source",
        remote_side="Source.id",
        foreign_keys=[parent_source_id],
    )
    excerpts: Mapped[list[SourceExcerpt]] = relationship(
        "SourceExcerpt",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="SourceExcerpt.position",
    )

    # La regle des titres et des auteurs, appliquee a chaque affectation : aucun
    # chemin d'ecriture ORM ne peut plus inscrire un titre de page anti-bot, un
    # segment d'adresse ou un profil en guise d'auteur (cf.
    # core/champs_bibliographiques.py). Un `update(Source).values(title=...)`
    # contournerait les validateurs : aucun n'ecrit ces deux champs aujourd'hui.
    @validates("title")
    def _valider_titre(self, _cle: str, valeur: str | None) -> str | None:
        return titre_bibliographique(valeur, self.url)

    @validates("authors")
    def _valider_auteurs(self, _cle: str, valeur: str | None) -> str | None:
        return auteurs_bibliographiques(valeur)

    @validates("url")
    def _revalider_titre_a_l_adresse(self, _cle: str, valeur: str) -> str:
        # Le titre a pu etre affecte avant l'adresse : c'est en tenant les deux
        # qu'on reconnait un titre qui n'est qu'un segment de l'adresse.
        titre = self.__dict__.get("title")
        if titre is not None and titre_bibliographique(titre, valeur) is None:
            self.title = None
        return valeur

    def __repr__(self) -> str:
        return f"<Source {self.title or self.url[:30]}>"


@event.listens_for(Source, "before_insert")
@event.listens_for(Source, "before_update")
def _imposer_la_nature(_mapper, _connexion, source: Source) -> None:
    """Format, categorie et auteur corriges quand une valeur neutre contredit les faits.

    A l'enregistrement plutot qu'a l'affectation : la regle croise l'adresse, le
    DOI et la revue, que les chemins d'ecriture affectent dans n'importe quel
    ordre (cf. core/nature_source.py). Un choix informatif n'est jamais ecrase.
    """
    nature = nature_corrigee(
        url=source.url,
        doi=source.doi,
        journal=source.journal,
        format=source.format,
        category=source.category,
        author_kind=source.author_kind,
    )
    source.format = nature.format
    source.category = nature.category
    source.author_kind = nature.author_kind
