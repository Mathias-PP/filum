"""Citations entrantes : qui s'appuie sur les fiches d'un createur.

Le lien fiche -> fiche est porte par ``Source.linked_card_id`` (voir
``card_link.py``). Le lire a l'envers donne la seule information qu'un createur
ne peut pas deduire de ses propres donnees : on l'a repris.

Trois regles de prudence, dans l'ordre ou elles comptent :

1. **Seules les fiches publiees ET publiques citent.** Un brouillon qui cite
   quelqu'un ne doit rien declencher : l'alerte revelerait l'existence d'un
   travail non publie, et le lien peut encore disparaitre.
2. **On ne s'auto-cite pas dans les alertes.** Relier deux de ses propres
   fiches est un acte d'edition, pas une reprise par un tiers.
3. **La date de la citation est celle ou elle est devenue publique**, soit
   ``max(source.created_at, citing_card.published_at)``. Une fiche redigee en
   brouillon pendant trois mois puis publiee aujourd'hui cite aujourd'hui ;
   dater la citation de la creation de la source la ferait naitre deja vue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User

# Plafond de la liste retournee. Au-dela, la page devient illisible et la
# requete couteuse ; le compteur de nouveautes, lui, reste exact.
MAX_CITATIONS = 200


@dataclass
class IncomingCitation:
    """Une fiche publique en cite une autre."""

    source_id: UUID
    cited_card_id: UUID
    cited_card_title: str
    cited_card_slug: str
    citing_card_id: UUID
    citing_card_title: str
    citing_card_slug: str
    citing_creator_slug: str
    citing_creator_name: str | None
    # Rapport declare par la source citante : appui, nuance, contradiction.
    # NULL = rien de declare, ce qui n'est pas la meme chose que neutre.
    stance: str | None
    cited_at: datetime
    is_new: bool


@dataclass
class IncomingCitations:
    citations: list[IncomingCitation]
    new_count: int
    # NULL = jamais consulte. Le frontend en a besoin pour dire « depuis
    # toujours » plutot que d'inventer une date.
    seen_at: datetime | None
    truncated: bool


async def list_incoming_citations(db: AsyncSession, user: User) -> IncomingCitations:
    """Les citations publiques vers les fiches de ``user``, les neuves d'abord."""
    citing_card = BiblioCard.__table__.alias("citing_card")
    cited_card = BiblioCard.__table__.alias("cited_card")

    stmt = (
        select(
            Source.id,
            Source.stance,
            Source.created_at,
            cited_card.c.id,
            cited_card.c.title,
            cited_card.c.slug,
            citing_card.c.id,
            citing_card.c.title,
            citing_card.c.slug,
            citing_card.c.published_at,
            User.username,
            User.display_name,
        )
        .select_from(Source)
        .join(cited_card, Source.linked_card_id == cited_card.c.id)
        .join(citing_card, Source.biblio_card_id == citing_card.c.id)
        .join(User, citing_card.c.user_id == User.id)
        .where(
            cited_card.c.user_id == user.id,
            cited_card.c.deleted_at.is_(None),
            # Regle 2 : une reprise par soi-meme n'est pas une reprise.
            citing_card.c.user_id != user.id,
            # Regle 1 : seul le publie et public compte.
            citing_card.c.status == "published",
            citing_card.c.visibility == "public",
            citing_card.c.deleted_at.is_(None),
            Source.deleted_at.is_(None),
        )
    )

    rows = (await db.execute(stmt)).all()
    seen_at = user.citations_seen_at

    citations: list[IncomingCitation] = []
    for row in rows:
        (
            source_id,
            stance,
            source_created_at,
            cited_id,
            cited_title,
            cited_slug,
            citing_id,
            citing_title,
            citing_slug,
            citing_published_at,
            username,
            display_name,
        ) = row
        # Regle 3. published_at peut manquer sur des fiches anterieures au
        # champ ; la date de la source fait alors foi, faute de mieux.
        cited_at = source_created_at
        if citing_published_at and citing_published_at > cited_at:
            cited_at = citing_published_at
        citations.append(
            IncomingCitation(
                source_id=source_id,
                cited_card_id=cited_id,
                cited_card_title=cited_title,
                cited_card_slug=cited_slug,
                citing_card_id=citing_id,
                citing_card_title=citing_title,
                citing_card_slug=citing_slug,
                citing_creator_slug=username,
                citing_creator_name=display_name,
                stance=stance,
                cited_at=cited_at,
                # seen_at NULL : jamais consulte, donc tout est neuf.
                is_new=seen_at is None or cited_at > seen_at,
            )
        )

    citations.sort(key=lambda c: c.cited_at, reverse=True)
    new_count = sum(1 for c in citations if c.is_new)
    truncated = len(citations) > MAX_CITATIONS
    return IncomingCitations(
        citations=citations[:MAX_CITATIONS],
        new_count=new_count,
        seen_at=seen_at,
        truncated=truncated,
    )


def mark_citations_seen(user: User) -> datetime:
    """Horodate la consultation. Naif-UTC comme le reste des colonnes DateTime.

    Un datetime tz-aware casse asyncpg sur une colonne ``TIMESTAMP WITHOUT
    TIME ZONE`` -- c'est le bug qui a coute quatre PRs en mai 2026.
    """
    user.citations_seen_at = datetime.now(UTC).replace(tzinfo=None)
    return user.citations_seen_at
