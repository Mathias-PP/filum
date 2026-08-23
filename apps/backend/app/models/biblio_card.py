from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.user import User


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class CardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


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


class CardKind(str, Enum):
    """Ce qu'une fiche documente, et donc qui en est l'auteur.

    - CONTENU : une video, un article, un post qui existe ailleurs. La fiche
      porte son URL et ses auteurs, qui ne sont pas le createur Philum tant
      qu'il ne s'en declare pas l'auteur (`is_seed`).
    - SUJET : une bibliographie sur une question. Il n'y a pas de contenu
      source, donc pas d'URL ni d'auteurs tiers : la synthese est du createur.
    """

    CONTENU = "contenu"
    SUJET = "sujet"


class Visibility(str, Enum):
    """Qui peut voir une fiche une fois publiee.

    - PUBLIC  : visible par tout le monde (comportement historique, default DB).
    - PRIVATE : visible uniquement par son owner connecte.
    """

    PUBLIC = "public"
    PRIVATE = "private"


class BiblioCard(Base):
    __tablename__ = "biblio_cards"
    __table_args__ = (Index("ix_biblio_cards_user_status", "user_id", "status"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nature de la fiche. NOT NULL avec defaut `contenu` : c'est ce qu'etaient
    # toutes les fiches avant que la nature existe.
    card_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="contenu", server_default="contenu"
    )
    # `content_type` et `platform` decrivent le contenu documente : NULL sur
    # une fiche sujet, qui n'en documente aucun.
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Auteurs du contenu documente, qui ne sont pas ceux de la fiche : publier
    # une fiche n'est pas signer ce qu'elle documente. Sans cette colonne, les
    # auteurs n'existaient que dans la bibliographie des fiches citantes, et
    # une fiche que personne ne cite ne pouvait porter que le nom de son
    # createur Philum -- exactement le contresens a eviter.
    content_authors: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Referencement du contenu documente, meme vocabulaire que les sources
    # (`SourceFormat`, `SourceCategory`, `AuthorKind`) : une fiche devient une
    # reference des qu'une autre la cite, et doit se lire dans la meme grille.
    # NULL = non declare, jamais une valeur par defaut.
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    author_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Texte integral du contenu documente quand le createur en dispose et a
    #: le droit de le publier : son propre article, un contenu libre de droit,
    #: une retranscription qu'il a faite, un extrait sous droit de citation.
    #: Rendu sur la fiche publique et indexable par les tools MCP en aval.
    #: Longueur pratique bornee cote endpoint (upload/paste), pas cote colonne.
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        index=True,
    )
    is_seed: Mapped[bool] = mapped_column(default=False, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="public",
        server_default="public",
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="biblio_cards",
        foreign_keys=[user_id],
    )
    sources: Mapped[list[Source]] = relationship(
        "Source",
        back_populates="biblio_card",
        foreign_keys="Source.biblio_card_id",
        cascade="all, delete-orphan",
        order_by="Source.position",
    )

    def __repr__(self) -> str:
        return f"<BiblioCard {self.slug}>"
