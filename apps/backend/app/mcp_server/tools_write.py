"""Fonctions d'ecriture cote MCP.

Une IA connectee au MCP doit pouvoir produire une fiche complete sans
detour par le web : creer un brouillon, y ajouter les sources qu'elle a
lues, coller un extrait verbatim quand elle en tient un, publier. Chacune
de ces fonctions delegue au meme modele que le REST plutot que d'inventer
un chemin parallele : une seule fois la logique metier, une seule fois
les invariants (unicite du slug, propriete de la ressource, capacite
maximale, dedup de source par identite du contenu).

Le retour est volontairement compact : l'agent enchaine `add_source` puis
`add_excerpt` sur des dizaines de references, et charger a chaque appel le
detail complet gaspille sa fenetre de tokens.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastmcp.exceptions import ToolError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard, CardStatus
from app.models.source import Source
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.schemas.biblio_card import CardCreate, ContentType, Platform, Visibility
from app.services.card import CardService
from app.services.card_link import effective_linked_card_id
from app.services.content_identity import extract_doi, normalize_url
from app.services.excerpt_guards import LONGUEUR_MIN_AUTONOME_MOTS, passage_a_besoin_de_contexte
from app.services.excerpt_indexing import indexer_sans_bruit
from app.services.wayback import horodatage_wayback

# Meme limite que l'endpoint REST : au dela, l'agent noie sa fenetre et le
# lecteur perd de vue le fil du passage.
_EXTRAITS_MAX_PAR_SOURCE = 12


async def _fiche_du_createur(db: AsyncSession, user: User, slug: str) -> BiblioCard:
    """La fiche `slug` de `user`. Leve si elle n'existe pas ou appartient a autrui.

    On refuse de dire « existe mais pas a vous » : cela revelerait indirectement
    l'existence d'une fiche privee d'un autre createur.
    """
    stmt = select(BiblioCard).where(
        BiblioCard.user_id == user.id,
        BiblioCard.slug == slug,
        BiblioCard.deleted_at.is_(None),
    )
    card = (await db.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise ToolError(f"Aucune fiche {slug!r} chez {user.username}.")
    return card


def _identite(url: str | None, doi: str | None) -> str | None:
    """La cle d'identite d'une source : DOI en priorite, URL normalisee sinon."""
    if key := extract_doi(doi) or extract_doi(url):
        return f"doi:{key}"
    if norm := normalize_url(url):
        return f"url:{norm}"
    return None


async def _identites_deja_citees(db: AsyncSession, card_id: UUID) -> set[str]:
    stmt = select(Source.url, Source.doi).where(
        Source.biblio_card_id == card_id, Source.deleted_at.is_(None)
    )
    return {k for (u, d) in (await db.execute(stmt)).all() if (k := _identite(u, d))}


async def create_card(
    db: AsyncSession,
    user: User,
    *,
    slug: str,
    title: str,
    content_url: str | None = None,
    description: str | None = None,
    content_authors: str | None = None,
    platform: str = "other",
    content_type: str = "article",
    visibility: str = "public",
) -> dict[str, Any]:
    """Cree un brouillon. La publication est un geste distinct (`publish_card`)."""
    try:
        payload = CardCreate(
            slug=slug,
            title=title,
            description=description,
            content_url=content_url,
            content_authors=content_authors,
            platform=Platform(platform),
            content_type=ContentType(content_type),
            visibility=Visibility(visibility),
        )
    except ValueError as exc:
        # Un slug invalide ou une enumeration hors du vocabulaire est un
        # message que l'agent peut lire et corriger : le lui rendre en clair.
        raise ToolError(str(exc)) from exc
    service = CardService(db)
    #: Pas de contrainte d'unicite en base : c'est l'endpoint REST qui refuse
    #: le doublon, et le MCP doit le refuser pareil.
    if await service.get_card_by_slug(user.username, payload.slug, published_only=False):
        raise ToolError(f"Une fiche {slug!r} existe deja chez {user.username}.")
    try:
        card = await service.create_card(user.id, payload)
    except IntegrityError as exc:
        await db.rollback()
        raise ToolError(f"Une fiche {slug!r} existe deja chez {user.username}.") from exc
    return {
        "creator": user.username,
        "slug": card.slug,
        "status": card.status,
        "public_url_when_published": (
            f"https://philum-eight.vercel.app/@{user.username}/{card.slug}"
        ),
    }


async def add_source(
    db: AsyncSession,
    user: User,
    *,
    card_slug: str,
    url: str = "",
    title: str | None = None,
    authors: str | None = None,
    doi: str | None = None,
    category: str = "article-scientifique",
    author_kind: str = "chercheur",
    format: str = "texte",
    stance: str | None = None,
    annotation: str | None = None,
    journal: str | None = None,
    archive_url: str | None = None,
) -> dict[str, Any]:
    """Ajoute une source a la fiche. Ne declenche pas l'archivage automatique :
    un agent qui tient une capture Wayback peut la donner via `archive_url`,
    sinon la source reste `pending` et sera archivee au prochain passage cote UI.
    """
    card = await _fiche_du_createur(db, user, card_slug)

    cle = _identite(url, doi)
    if cle and cle in await _identites_deja_citees(db, card.id):
        raise ToolError(f"Cette source figure deja dans {card_slug!r}.")

    max_position = await db.scalar(
        select(func.max(Source.position)).where(Source.biblio_card_id == card.id)
    )
    manual_archive = (archive_url or "").strip() or None

    try:
        linked_card_id = await effective_linked_card_id(
            db,
            chosen=None,
            url=url,
            user_id=user.id,
            current_card_id=card.id,
            doi=doi,
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    source = Source(
        biblio_card_id=card.id,
        position=(max_position or 0) + 1,
        url=url,
        title=title,
        authors=authors,
        format=format,
        category=category,
        author_kind=author_kind,
        stance=stance,
        annotation=annotation,
        journal=journal,
        doi=doi,
        linked_card_id=linked_card_id,
        archive_url=manual_archive,
        archive_status="archived" if manual_archive else "pending",
        archive_timestamp=horodatage_wayback(manual_archive),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {
        "id": str(source.id),
        "card_slug": card.slug,
        "position": source.position,
        "linked_card_id": str(source.linked_card_id) if source.linked_card_id else None,
    }


async def add_excerpt(
    db: AsyncSession,
    user: User,
    *,
    source_id: str,
    text: str,
    title: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Ajoute un verbatim a une source. Marque `annotated_by_ai=True` : cette
    reponse porte les extraits qu'un modele a produits, le distinguer preserve
    la separation entre ce que la source dit et ce qu'une IA en dit."""
    try:
        sid = UUID(source_id)
    except ValueError as exc:
        raise ToolError(f"Identifiant de source invalide : {source_id!r}.") from exc

    stmt = (
        select(Source)
        .join(BiblioCard, Source.biblio_card_id == BiblioCard.id)
        .where(
            Source.id == sid,
            Source.deleted_at.is_(None),
            BiblioCard.user_id == user.id,
            BiblioCard.deleted_at.is_(None),
        )
    )
    source = (await db.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise ToolError(f"Aucune source {source_id!r} chez {user.username}.")

    corps = (text or "").strip()
    if not corps:
        raise ToolError("Un extrait vide ne cite rien.")

    # Garde-fou anti extrait hors-contexte : un extrait court qui commence
    # par un pronom ou un demonstratif sans referent visible devient un
    # contresens cite seul (« cela ameliore la memoire » sans « cela »
    # nomme). L'agent doit alors soit elargir le passage pour inclure
    # l'antecedent, soit fournir une mise en situation explicite via
    # `context` (qui nomme le referent en clair).
    contexte_donne = (context or "").strip()
    if (
        len(corps.split()) < LONGUEUR_MIN_AUTONOME_MOTS
        and passage_a_besoin_de_contexte(corps)
        and not contexte_donne
    ):
        raise ToolError(
            "Extrait trop court et referentiel (commence par « cela »/« ces »/etc. "
            "sans antecedent visible). Soit elargir l'extrait pour inclure la "
            "phrase qui donne le sens, soit fournir un `context` qui nomme en "
            "clair ce a quoi renvoient les pronoms et les demonstratifs. Cite "
            "seul, un tel extrait pousse au contresens."
        )

    count = await db.scalar(
        select(func.count()).select_from(SourceExcerpt).where(SourceExcerpt.source_id == source.id)
    )
    if (count or 0) >= _EXTRAITS_MAX_PAR_SOURCE:
        raise ToolError(f"Une source ne porte pas plus de {_EXTRAITS_MAX_PAR_SOURCE} extraits.")

    max_pos = await db.scalar(
        select(func.max(SourceExcerpt.position)).where(SourceExcerpt.source_id == source.id)
    )
    excerpt = SourceExcerpt(
        source_id=source.id,
        position=(max_pos or 0) + 1,
        text=corps,
        title=(title or "").strip() or None,
        context=(context or "").strip() or None,
        # L'agent qui appelle ce tool est une IA : le dire au consommateur.
        suggested_by_ai=True,
        annotated_by_ai=True,
    )
    db.add(excerpt)
    await db.commit()
    await db.refresh(excerpt)
    await indexer_sans_bruit(db, [excerpt])
    return {
        "id": str(excerpt.id),
        "source_id": str(source.id),
        "position": excerpt.position,
    }


#: Meme borne que le schema CardBase.content_text. 500 000 caracteres = un
#: roman entier ; au-dela, c'est un corpus, sa voie est le decoupage en fiches.
_MAX_CONTENT_TEXT = 500_000


async def set_content_text(
    db: AsyncSession,
    user: User,
    *,
    card_slug: str,
    text: str,
    confirm_publication_rights: bool,
) -> dict[str, Any]:
    """Pose le texte integral du contenu documente sur la fiche `card_slug`.

    Le texte est rendu tel quel sur la fiche publique. Un agent qui l'appelle
    a la place de l'utilisateur porte la meme responsabilite que lui : il doit
    savoir avoir le droit de publier ce texte (contenu propre, libre de droit,
    ou extrait sous droit de citation). Le drapeau `confirm_publication_rights`
    exige que ce choix soit explicite -- passer `False` refuse la pose, passer
    `True` engage la responsabilite du compte qui appelle.

    Chaine vide = retire le texte precedemment pose (l'affichage sur la fiche
    publique disparait).
    """
    if not confirm_publication_rights:
        raise ToolError(
            "Passer confirm_publication_rights=true pour publier ce texte. "
            "L'agent doit avoir constate que le contenu est publiable (contenu "
            "propre, libre de droit, ou droit de citation dans les limites)."
        )
    if len(text) > _MAX_CONTENT_TEXT:
        raise ToolError(
            f"Texte trop long ({len(text)} caracteres, maximum {_MAX_CONTENT_TEXT:_}). "
            "Decoupez le contenu en plusieurs fiches (une par chapitre / episode)."
        )
    card = await _fiche_du_createur(db, user, card_slug)
    card.content_text = text or None
    await db.commit()
    return {
        "creator": user.username,
        "slug": card.slug,
        "content_text_length": len(text),
        "content_text_cleared": not bool(text),
    }


async def publish_card(db: AsyncSession, user: User, *, slug: str) -> dict[str, Any]:
    """Rend la fiche visible sur le web. Republier une fiche deja publique est
    un no-op cote feed : le registre du premier passage au public reste unique."""
    stmt = (
        select(BiblioCard)
        .options(selectinload(BiblioCard.user))
        .where(
            BiblioCard.user_id == user.id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    card = (await db.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise ToolError(f"Aucune fiche {slug!r} chez {user.username}.")
    service = CardService(db)
    published = await service.publish_card(card)
    return {
        "creator": user.username,
        "slug": slug,
        "status": CardStatus.PUBLISHED.value,
        "published_at": published["published_at"].isoformat(),
        "public_url": published["public_url"],
    }
