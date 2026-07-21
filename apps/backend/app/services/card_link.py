"""Detection des URLs pointant vers une fiche Philum publique.

Une source dont l'URL est une fiche Philum (/@{username}/{slug}) devient une
"fiche parente" : on stocke son id dans Source.linked_card_id pour permettre
la navigation entre fiches.

La detection est restreinte aux hosts de notre propre frontend pour eviter
les faux positifs (medium.com/@user/slug a la meme forme de path).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.biblio_card import BiblioCard
from app.models.user import User

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
