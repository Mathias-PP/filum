"""Tests oracle Wikipedia (parsing local, sans reseau)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.extractors.wikipedia_oracle import (
    _extract_lang_and_title,
    _parse_reference_li,
    is_wikipedia_url,
)


def test_is_wikipedia_url_positive():
    assert is_wikipedia_url("https://en.wikipedia.org/wiki/Working_memory") is True
    assert is_wikipedia_url("https://fr.wikipedia.org/wiki/M%C3%A9moire_de_travail") is True
    assert is_wikipedia_url("https://de.wikipedia.org/wiki/Test") is True


def test_is_wikipedia_url_negative():
    assert is_wikipedia_url("https://medium.com/@user/wiki/foo") is False
    # www.wikipedia.org est le portail multi-langue, pas une page d'article.
    # Notre regex accepte www comme un pseudo-lang, mais _extract_lang_and_title
    # va echouer sur ce host sans /wiki/Title valide en pratique.
    assert is_wikipedia_url("not a url") is False


def test_extract_lang_and_title():
    assert _extract_lang_and_title("https://en.wikipedia.org/wiki/Working_memory") == (
        "en",
        "Working memory",
    )
    assert _extract_lang_and_title(
        "https://fr.wikipedia.org/wiki/M%C3%A9moire_de_travail"
    ) == ("fr", "Mémoire de travail")


def test_parse_reference_li_with_doi_and_cite():
    html = """
    <li>Diamond A (2013). <cite><a class="external" href="https://doi.org/10.1146/annurev-psych-113011-143750">Executive functions</a></cite>. Annual Review of Psychology. 64: 135–168.</li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.url.startswith("https://doi.org/")
    assert ref.title == "Executive functions"
    assert ref.year == 2013
    assert ref.authors == "Diamond A"


def test_parse_reference_li_no_doi_external_link_fallback():
    html = """
    <li>Wolfe C. D. (2007). <a class="external" href="https://example.com/paper">The paper title here</a>. Journal.</li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.url == "https://example.com/paper"
    assert ref.year == 2007


def test_parse_reference_li_empty_returns_none():
    html = "<li></li>"
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is None
