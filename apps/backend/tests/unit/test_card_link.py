"""Tests de detection des URLs de fiches Philum (services/card_link)."""

from __future__ import annotations

from app.services.card_link import parse_public_card_path


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
