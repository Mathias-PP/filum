"""Tests du filtre « liens de l'auteur·ice » sur une description YouTube.

Mesure du 2026-08-07 sur la video 3Blue1Brown *But what is a neural network?* :
sur 16 sources extraites, 11 etaient le bloc de signature de la chaine
(Patreon deux fois, ses propres sites, Bandcamp, Spotify, Twitter, Facebook,
Reddit). Ce bloc est identique dans toutes les videos de l'auteur : il ne dit
rien de ce que cette video-la s'appuie sur.
"""

from __future__ import annotations

from app.extractors.youtube_oracle import (
    extract_channel_name_from_html,
    is_creator_self_link,
)


def test_lit_le_nom_de_chaine_dans_la_page():
    html = 'var x = ytInitialPlayerResponse = {"videoDetails":{"author":"3Blue1Brown"}};'
    assert extract_channel_name_from_html(html) == "3Blue1Brown"


def test_nom_de_chaine_absent():
    assert extract_channel_name_from_html("<html></html>") is None


def test_ecarte_les_proprietes_de_l_auteur():
    for url in (
        "https://www.patreon.com/3blue1brown",
        "https://www.3blue1brown.com/topics/neural-networks",
        "https://twitter.com/3Blue1Brown",
        "https://www.facebook.com/3blue1brown",
        "https://www.reddit.com/r/3Blue1Brown",
    ):
        assert is_creator_self_link(url, None, "3Blue1Brown") is True, url


def test_ecarte_via_le_titre_quand_l_url_ne_porte_pas_le_nom():
    """L'album Spotify a une URL opaque ; son titre trahit l'appartenance."""
    assert (
        is_creator_self_link(
            "https://open.spotify.com/album/1dVyjwS8FBqXhRunaG5W5u",
            "The Music of 3blue1brown - Album by Vincent Rubinetti",
            "3Blue1Brown",
        )
        is True
    )


def test_garde_les_vraies_sources():
    for url, titre in (
        ("http://colah.github.io/", "Home - colah's blog"),
        ("https://distill.pub/", "Latest articles about machine learning"),
        ("https://goo.gl/Zmczdy", "Neural networks and deep learning"),
        ("https://youtu.be/i8D90DkCLhI", "Learning To See [Part 1: Introduction]"),
    ):
        assert is_creator_self_link(url, titre, "3Blue1Brown") is False, url


def test_sans_nom_de_chaine_on_ne_filtre_rien():
    """Faute de savoir a qui est la chaine, tout filtrage serait arbitraire."""
    assert is_creator_self_link("https://www.patreon.com/3blue1brown", None, None) is False


def test_un_nom_de_chaine_trop_court_ne_filtre_pas():
    """« Vox » ou « ARTE » apparaissent dans des URLs sans rapport ; filtrer
    dessus emporterait de vraies sources."""
    assert is_creator_self_link("https://voxeurop.eu/article", None, "Vox") is False
