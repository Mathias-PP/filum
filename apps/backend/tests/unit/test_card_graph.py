"""Tests du service card_graph."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import AuthorKind, Source, SourceCategory, SourceFormat
from app.models.user import User
from app.services.card_graph import build_card_graph


async def _make_user(db, *, username: str) -> User:
    user = User(
        id=uuid4(),
        email=f"{username}@example.com",
        username=username,
        display_name=username.capitalize(),
        public_key="k" * 64,
        encrypted_private_key="encrypted_key",
        google_id=f"google_{username}",
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_card(db, user: User, *, slug: str, published: bool = True) -> BiblioCard:
    card = BiblioCard(
        id=uuid4(),
        user_id=user.id,
        slug=slug,
        title=f"Fiche {slug}",
        content_type=ContentType.ARTICLE.value,
        platform=Platform.BLOG.value,
        status=CardStatus.PUBLISHED.value if published else CardStatus.DRAFT.value,
        visibility="public",
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def _make_source(
    db, from_card: BiblioCard, *, linked_card: BiblioCard | None = None
) -> Source:
    source = Source(
        id=uuid4(),
        biblio_card_id=from_card.id,
        position=0,
        url="https://example.com/ref",
        title="Une reference",
        format=SourceFormat.TEXTE.value,
        category=SourceCategory.BLOG.value,
        author_kind=AuthorKind.INDIVIDU.value,
        linked_card_id=linked_card.id if linked_card else None,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@pytest_asyncio.fixture
async def two_users(db_session):
    owner = await _make_user(db_session, username="owner")
    neighbor = await _make_user(db_session, username="neighbor")
    return owner, neighbor


@pytest.mark.asyncio
async def test_source_liee_expose_le_chemin_de_sa_fiche(db_session, two_users):
    """Une source qui designe une fiche doit porter de quoi y aller.

    Sans slug ni createur, le lecteur voit « cette source est une fiche
    Philum » sans pouvoir l'ouvrir : une promesse sans porte.
    """
    owner, neighbor = two_users
    root_card = await _make_card(db_session, owner, slug="root-card")
    linked_card = await _make_card(db_session, neighbor, slug="neighbor-card")
    await _make_source(db_session, root_card, linked_card=linked_card)

    graph = await build_card_graph(db_session, root_card, depth=0)
    linked = [n for n in graph.nodes if n.kind == "source" and n.linked_card_id]
    assert linked, "le jeu de test doit contenir au moins une source liee"
    for node in linked:
        assert node.linked_card_slug
        assert node.linked_card_creator_slug
