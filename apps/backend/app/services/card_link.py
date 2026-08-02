"""Detection des fiches Philum designees par une source.

Deux chemins, du plus explicite au plus implicite :

1. L'URL de la source EST une fiche Philum (/@{username}/{slug}). La detection
   est restreinte aux hosts de notre propre frontend pour eviter les faux
   positifs (medium.com/@user/slug a la meme forme de path).
2. L'URL de la source designe le meme contenu qu'une fiche existante — meme
   DOI, ou meme URL normalisee que son ``content_url``. Une reference vers un
   article et la fiche qui documente cet article sont le meme objet ; sans
   cette resolution le meta-graphe l'affiche deux fois, une fois comme fiche
   et une fois comme source isolee, et ne les relie pas.

Le resultat est stocke dans Source.linked_card_id : c'est l'unique lien
fiche -> fiche, il porte tout le meta-graphe.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.services.content_identity import escape_like, extract_doi, url_variants

settings = get_settings()

_CARD_PATH_RE = re.compile(r"^/@([a-zA-Z0-9_.-]+)/([a-zA-Z0-9-]+)/?$")


def _allowed_hosts() -> set[str]:
    hosts = {"localhost", "127.0.0.1"}
    frontend_host = urlparse(settings.frontend_base_url).hostname
    if frontend_host:
        hosts.add(frontend_host.lower())
    return hosts


def parse_public_card_path(url: str) -> tuple[str, str] | None:
    """Retourne (username, slug) si l'URL est une fiche publique Philum."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if host not in _allowed_hosts():
        return None
    match = _CARD_PATH_RE.match(parsed.path)
    if not match:
        return None
    return match.group(1), match.group(2)


async def assert_linked_card_allowed(
    db: AsyncSession,
    linked_card_id: UUID,
    *,
    user_id: UUID,
    current_card_id: UUID,
) -> None:
    """Verifie qu'une fiche peut etre designee par une source. Leve ValueError sinon.

    Une fiche est une cible legitime si elle appartient a l'utilisateur (y
    compris en brouillon) ou si elle est publiee et publique — c'est-a-dire
    exactement ce que le picker propose. Sans cette verification, un id
    devine permettrait de rattacher une source a une fiche privee d'autrui
    et d'en confirmer l'existence.
    """
    if linked_card_id == current_card_id:
        raise ValueError("Une fiche ne peut pas se referencer elle-meme")
    stmt = select(BiblioCard.id).where(
        BiblioCard.id == linked_card_id,
        BiblioCard.deleted_at.is_(None),
    )
    card = (
        await db.execute(
            stmt.add_columns(BiblioCard.user_id, BiblioCard.status, BiblioCard.visibility)
        )
    ).first()
    if card is None:
        raise ValueError("Fiche liee introuvable")
    _, owner_id, card_status, visibility = card
    if owner_id == user_id:
        return
    if card_status == "published" and visibility == "public":
        return
    raise ValueError("Fiche liee inaccessible")


async def resolve_linked_card_id(
    db: AsyncSession,
    url: str,
    *,
    exclude_card_id: UUID | None = None,
) -> UUID | None:
    """Resout l'id de la fiche publique visee par l'URL, si elle existe.

    exclude_card_id evite qu'une fiche se reference elle-meme.
    """
    parsed = parse_public_card_path(url)
    if not parsed:
        return None
    username, slug = parsed
    stmt = (
        select(BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            User.username == username,
            BiblioCard.slug == slug,
            BiblioCard.status == "published",
            BiblioCard.visibility == "public",
            BiblioCard.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    card_id = result.scalar_one_or_none()
    if card_id is None or card_id == exclude_card_id:
        return None
    return card_id


async def resolve_card_by_content(
    db: AsyncSession,
    url: str,
    *,
    doi: str | None = None,
    exclude_card_id: UUID | None = None,
) -> UUID | None:
    """La fiche publique qui documente exactement ce contenu, si elle existe.

    On compare sur le DOI d'abord, sur l'URL normalisee ensuite. La fiche la
    plus ancienne gagne, pour que le graphe soit stable d'un appel a l'autre
    si deux fiches documentent le meme contenu.
    """
    clauses = []
    variants = url_variants(url)
    if variants:
        clauses.append(BiblioCard.content_url.in_(variants))
    key_doi = extract_doi(doi) or extract_doi(url)
    if key_doi:
        clauses.append(BiblioCard.content_url.ilike(f"%{escape_like(key_doi)}%", escape="\\"))
    if not clauses:
        return None

    result = await db.execute(
        select(BiblioCard.id)
        .where(
            or_(*clauses),
            BiblioCard.content_url.is_not(None),
            BiblioCard.status == "published",
            BiblioCard.visibility == "public",
            BiblioCard.deleted_at.is_(None),
        )
        .order_by(BiblioCard.created_at)
    )
    for row in result.all():
        card_id: UUID = row[0]
        if card_id != exclude_card_id:
            return card_id
    return None


async def link_sources_designating_card(db: AsyncSession, card: BiblioCard) -> None:
    """Rattache a ``card`` les sources deja saisies qui designent son contenu.

    Une fiche est souvent creee apres les sources qui la citent : la fiche
    d'un article existe parce que quelqu'un l'a cite. Sans ce rattrapage, le
    lien ne vaudrait que pour les sources saisies ensuite, et les references
    anterieures resteraient isolees sur le graphe.
    """
    if not card.content_url:
        return
    clauses = []
    variants = url_variants(card.content_url)
    if variants:
        clauses.append(Source.url.in_(variants))
    key_doi = extract_doi(card.content_url)
    if key_doi:
        pattern = f"%{escape_like(key_doi)}%"
        clauses.append(Source.doi.ilike(pattern, escape="\\"))
        clauses.append(Source.url.ilike(pattern, escape="\\"))
    if not clauses:
        return

    await db.execute(
        update(Source)
        .where(
            or_(*clauses),
            Source.linked_card_id.is_(None),
            Source.biblio_card_id != card.id,
            Source.deleted_at.is_(None),
        )
        .values(linked_card_id=card.id)
    )


async def effective_linked_card_id(
    db: AsyncSession,
    *,
    chosen: UUID | None,
    url: str,
    user_id: UUID,
    current_card_id: UUID,
    doi: str | None = None,
) -> UUID | None:
    """Le lien fiche d'une source : le picker, l'URL Philum, sinon le contenu.

    Un seul chemin pour la creation, le batch et l'edition : c'est ce qui
    manquait, l'edition perdait le lien faute de le recalculer.
    """
    if chosen is not None:
        await assert_linked_card_allowed(
            db, chosen, user_id=user_id, current_card_id=current_card_id
        )
        return chosen
    by_path = await resolve_linked_card_id(db, url, exclude_card_id=current_card_id)
    if by_path is not None:
        return by_path
    return await resolve_card_by_content(db, url, doi=doi, exclude_card_id=current_card_id)
