"""Tests de detection des URLs de fiches Philum (services/card_link)."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.user import User
from app.services.card_link import LinkOrigin, LinkResolution, parse_public_card_path, resolve_link


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


async def _make_card(db, user: User, *, slug: str, content_url: str | None = None) -> BiblioCard:
    card = BiblioCard(
        id=uuid4(),
        user_id=user.id,
        slug=slug,
        title=f"Fiche {slug}",
        content_type=ContentType.ARTICLE.value,
        platform=Platform.BLOG.value,
        status=CardStatus.PUBLISHED.value,
        visibility="public",
        content_url=content_url,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@pytest_asyncio.fixture
async def user(db_session):
    return await _make_user(db_session, username="alice")


@pytest_asyncio.fixture
async def card(db_session, user):
    return await _make_card(db_session, user, slug="ma-fiche")


@pytest_asyncio.fixture
async def other_user(db_session):
    return await _make_user(db_session, username="bob")


@pytest_asyncio.fixture
async def other_card(db_session, other_user):
    return await _make_card(
        db_session,
        other_user,
        slug="autre-fiche",
        content_url="https://example.com/article",
    )


@pytest.mark.asyncio
async def test_lien_choisi_est_confirme(db_session, user, card, other_card):
    """Choisir une fiche dans le selecteur vaut confirmation."""
    result = await resolve_link(
        db_session,
        chosen=other_card.id,
        url="https://exemple.test/article",
        user_id=user.id,
        current_card_id=card.id,
    )
    assert result.card_id == other_card.id
    assert result.origin == LinkOrigin.MANUEL
    assert result.confirmed is True


@pytest.mark.asyncio
async def test_lien_deduit_du_contenu_reste_une_suggestion(db_session, user, card, other_card):
    """Un meme contenu est une hypothese, pas une declaration du createur."""
    result = await resolve_link(
        db_session,
        chosen=None,
        url=other_card.content_url,
        user_id=user.id,
        current_card_id=card.id,
    )
    assert result.card_id == other_card.id
    assert result.origin == LinkOrigin.CONTENU
    assert result.confirmed is False


def test_localhost_card_url_parsed():
    assert parse_public_card_path("http://localhost:5173/@alice/memoire-et-cerveau") == (
        "alice",
        "memoire-et-cerveau",
    )


def test_frontend_host_card_url_parsed(monkeypatch):
    from app.services import card_link

    monkeypatch.setattr(
        card_link.settings, "frontend_base_url", "https://philum.example.com", raising=False
    )
    assert parse_public_card_path("https://philum.example.com/@bob/ma-fiche") == (
        "bob",
        "ma-fiche",
    )


def test_trailing_slash_accepted():
    assert parse_public_card_path("http://localhost:5173/@alice/ma-fiche/") == (
        "alice",
        "ma-fiche",
    )


def test_medium_like_url_rejected():
    # Meme forme de path, mais host etranger : pas une fiche Philum.
    assert parse_public_card_path("https://medium.com/@user/some-post") is None


def test_non_card_paths_rejected():
    assert parse_public_card_path("http://localhost:5173/dashboard") is None
    assert parse_public_card_path("http://localhost:5173/@alice") is None
    assert parse_public_card_path("http://localhost:5173/@alice/fiche/extra") is None


def test_non_http_scheme_rejected():
    assert parse_public_card_path("ftp://localhost/@alice/fiche") is None
    assert parse_public_card_path("not a url") is None
