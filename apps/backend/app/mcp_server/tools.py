"""Fonctions read-only du serveur MCP.

Fonctions pures (session en parametre) pour rester testables sans le
protocole MCP. Reponses volontairement compactes : l'IA cliente ne charge
que les noeuds qu'elle visite (frugalite en tokens).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.services.card_search import correspond
from app.services.content_identity import escape_like, extract_doi, url_variants

# Le seul filtre qui vaille pour une surface publique et anonyme.
#
# `status == "published"` decrit l'avancement du travail, pas l'audience : une
# fiche peut etre achevee et signee sans etre offerte au monde. C'est
# `visibility` qui tranche, et toutes les routes REST publiques le verifiaient
# deja (cards.py, users.py). Le MCP ne le faisait pas, et livrait donc a qui le
# demandait le titre, la description, l'URL du contenu et la bibliographie
# complete de fiches que leur auteur avait gardees privees.
_PUBLIC = (
    (BiblioCard.status == "published")
    & (BiblioCard.visibility == "public")
    & BiblioCard.deleted_at.is_(None)
)


def _arete_vers_une_fiche(source: Source) -> dict[str, str] | None:
    """L'adresse de la fiche Philum que cette source designe, si elle est ouverte.

    C'est l'unique arete fiche -> fiche, celle qui fait du corpus un graphe
    plutot qu'une collection de listes. Sans elle, un agent lisant une
    bibliographie de cent references ignore que deux d'entre elles sont
    elles-memes documentees ici, avec leurs propres extraits verifies.

    Le lien a pu etre pose quand la fiche citee etait publique : on reverifie
    a la lecture, sinon le MCP publierait le slug d'un travail retire du monde.
    """
    citee = source.linked_card
    if citee is None or citee.deleted_at is not None:
        return None
    if citee.status != "published" or citee.visibility != "public":
        return None
    return {"creator": citee.user.username, "slug": citee.slug}


async def search_cards(db: AsyncSession, query: str, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            _PUBLIC,
            # Le meme predicat que /discover, bibliographie comprise. Un agent
            # formule une intention (« consolidation du sommeil »), pas un
            # titre exact, et il cherche le plus souvent un travail cite : sans
            # les sources, « engram » ne ramenait rien d'un corpus qui en porte
            # un extrait verifie.
            #
            # `contient` replie aussi les accents : un agent redemande souvent
            # un titre qu'il a lu translittere, et « memoire » doit atteindre
            # « Mémoire et cerveau ».
            correspond(query),
        )
        .options(selectinload(BiblioCard.user))
        .order_by(BiblioCard.published_at.desc())
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]


async def get_card(db: AsyncSession, creator: str, slug: str) -> dict[str, Any] | None:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLIC, User.username == creator, BiblioCard.slug == slug)
        .options(
            selectinload(BiblioCard.user),
            selectinload(BiblioCard.sources)
            .selectinload(Source.linked_card)
            .selectinload(BiblioCard.user),
        )
    )
    card = await db.scalar(stmt)
    if card is None:
        return None
    return {
        "creator": card.user.username,
        "slug": card.slug,
        "title": card.title,
        "description": card.description,
        "content_url": card.content_url,
        "published_at": card.published_at.isoformat() if card.published_at else None,
        "sources": [
            {
                "id": str(s.id),
                "title": s.title,
                "url": s.url,
                "category": s.category,
                "author_kind": s.author_kind,
                #: `null` se dit, pour qu'un agent sache que la question a ete
                #: posee et non omise.
                "linked_card": _arete_vers_une_fiche(s),
            }
            for s in card.sources
            if s.deleted_at is None
        ],
    }


async def get_source(db: AsyncSession, source_id: str) -> dict[str, Any] | None:
    try:
        sid = UUID(source_id)
    except ValueError:
        return None
    source = await db.scalar(
        select(Source)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .where(_PUBLIC, Source.id == sid, Source.deleted_at.is_(None))
        .options(
            selectinload(Source.excerpts),
            selectinload(Source.linked_card).selectinload(BiblioCard.user),
        )
    )
    if source is None:
        return None
    return {
        "id": str(source.id),
        "title": source.title,
        "url": source.url,
        "authors": source.authors,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "format": source.format,
        "category": source.category,
        "author_kind": source.author_kind,
        "annotation": source.annotation,
        "doi": source.doi,
        "journal": source.journal,
        "publisher": source.publisher,
        # La relation declaree entre le propos du contenu et la source. Un agent
        # qui l'ignore lira « cite par » la ou le createur a ecrit « contredit ».
        "stance": source.stance,
        # Le seul champ dont l'omission peut faire propager une source retiree.
        "retraction_status": source.retraction_status,
        "retraction_notice_doi": source.retraction_notice_doi,
        "oa_status": source.oa_status,
        "oa_url": source.oa_url,
        "linked_card": _arete_vers_une_fiche(source),
        "archive_url": source.archive_url,
        "archive_timestamp": (
            source.archive_timestamp.isoformat() if source.archive_timestamp else None
        ),
        # Le verbatim, avec ce qui le situe et ce qui l'atteste. C'est ici que
        # la frugalite en tokens coutait le plus cher : un agent obtenait moins
        # d'une source par MCP que n'importe qui en telechargeant le CSV.
        "excerpts": [
            {
                "position": e.position,
                "title": e.title,
                "text": e.text,
                #: Situe le passage. Separe du verbatim, et jamais recolle
                #: dedans : le confondre attribuerait a la source des mots
                #: qu'elle n'a pas ecrits.
                "context": e.context,
                "suggested_by_ai": e.suggested_by_ai,
                "annotated_by_ai": e.annotated_by_ai,
                #: `null` = jamais relu, ce qui n'est pas « relu et introuvable ».
                "verified_at": e.verified_at.isoformat() if e.verified_at else None,
                "verified_status": e.verified_status,
                "verified_text_source": e.verified_text_source,
            }
            for e in sorted(source.excerpts, key=lambda e: e.position)
        ],
    }


async def find_cards_citing(db: AsyncSession, url: str, limit: int = 10) -> list[dict[str, Any]]:
    # Le meme critere d'identite que le reste du produit (`content_identity`) :
    # une arete du graphe ne peut pas dependre de l'ecriture de l'URL. Un agent
    # recopie ce qu'il a lu, avec ou sans `www.`, en `http`, avec la barre
    # finale ou le parametre de campagne colle par la page qui l'a mene la.
    # Comparer caractere par caractere rendait le graphe muet sur toutes ces
    # ecritures, et l'agent en concluait que personne ne citait la reference.
    clauses = []
    if variants := url_variants(url):
        clauses.append(Source.url.in_(variants))
    # L'agent tient souvent le DOI quand la fiche tient l'URL de l'editeur, et
    # l'inverse. Les deux designent le meme travail.
    if key_doi := extract_doi(url):
        motif = f"%{escape_like(key_doi)}%"
        clauses.append(Source.doi.ilike(motif, escape="\\"))
        clauses.append(Source.url.ilike(motif, escape="\\"))
    # Une URL illisible ne vaut pas « toutes les fiches ».
    if not clauses:
        return []

    stmt = (
        select(BiblioCard)
        .join(Source, Source.biblio_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLIC, Source.deleted_at.is_(None), or_(*clauses))
        .options(selectinload(BiblioCard.user))
        .distinct()
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]
