"""Tests oracle YouTube (parsing local, sans reseau)."""

from __future__ import annotations

import json

from app.extractors.youtube_oracle import (
    extract_description_from_html,
    is_youtube_url,
)


def test_is_youtube_url_positive():
    assert is_youtube_url("https://www.youtube.com/watch?v=x0g3571mS_M") is True
    assert is_youtube_url("https://youtu.be/x0g3571mS_M") is True
    assert is_youtube_url("https://m.youtube.com/watch?v=abc") is True
    assert is_youtube_url("https://www.youtube-nocookie.com/embed/abc") is True


def test_is_youtube_url_negative():
    assert is_youtube_url("https://notyoutube.com/watch?v=abc") is False
    assert is_youtube_url("https://example.com/youtube.com/watch") is False
    assert is_youtube_url("") is False


def _page(description: str) -> str:
    payload = {"videoDetails": {"videoId": "abc", "shortDescription": description}}
    return (
        "<html><body><script>var ytInitialPlayerResponse = "
        + json.dumps(payload)
        + ";var meta = {};</script></body></html>"
    )


def test_extract_description_full_text_not_truncated():
    description = "Sources :\nhttps://www.ameli.fr/assure/sante/themes/diabete\n" + "x" * 3000
    assert extract_description_from_html(_page(description)) == description


def test_extract_description_handles_escaped_braces_and_quotes():
    # La description contient des caracteres qui cassent une regex naive
    # de fermeture d'accolade : on valide que raw_decode s'en sort.
    description = 'Un {objet} et une "citation" puis } seul'
    assert extract_description_from_html(_page(description)) == description


def test_extract_description_absent_returns_none():
    assert extract_description_from_html("<html><body>rien</body></html>") is None
    assert extract_description_from_html(_page("   ")) is None


def test_extract_description_malformed_json_returns_none():
    html = "<script>var ytInitialPlayerResponse = {not json;</script>"
    assert extract_description_from_html(html) is None
