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
    assert _extract_lang_and_title("https://fr.wikipedia.org/wiki/M%C3%A9moire_de_travail") == (
        "fr",
        "Mémoire de travail",
    )


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


# --- L'etiquette d'un identifiant n'est pas un titre ------------------------
#
# Mesure en production sur `Working_memory` : sur 186 references extraites,
# cinq portaient « ISBN » ou « doi » comme intitule. Le modele `cite book`
# rend ses identifiants sous forme de liens dont le libelle est le nom de
# l'identifiant, et ce lien est le premier du <cite> quand la reference n'a
# pas d'URL de titre.


def test_isbn_ne_tient_pas_lieu_de_titre():
    html = """
    <li>Baddeley A. (2007). <cite class="citation book">Working memory, thought, and action.
    Oxford University Press. <a href="/wiki/Special:BookSources/978-0-19-852801-2">ISBN</a>
    978-0-19-852801-2</cite></li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.title != "ISBN"
    assert ref.title is not None
    assert "Working memory" in ref.title
    assert ref.year == 2007


def test_doi_ne_tient_pas_lieu_de_titre():
    # Le lien doi.org donne l'URL, pas l'intitule.
    html = """
    <li>Cowan N. (2001). <cite class="citation journal">The magical number four in short-term
    memory. Behavioral and Brain Sciences. 24: 87–114.
    <a class="external" href="https://doi.org/10.1017%2FS0140525X01003922">doi</a>:10.1017</cite></li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.url.startswith("https://doi.org/")
    assert ref.title is not None
    assert ref.title.lower() != "doi"
    assert "magical number four" in ref.title


def test_une_valeur_d_identifiant_ne_tient_pas_lieu_de_titre():
    # Selon le modele, Wikipedia lie le nom de l'identifiant ou sa valeur.
    # « 978-0-521-58325-1 » et « 14523382 » sont aussi peu des titres que
    # « ISBN » et « PMID ».
    html = """
    <li>Miyake A, Shah P (1999). <cite class="citation book">Models of working memory.
    Cambridge University Press. ISBN
    <a href="/wiki/Special:BookSources/978-0-521-58325-1">978-0-521-58325-1</a></cite></li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.title is not None
    assert "Models of working memory" in ref.title


def test_un_titre_court_mais_legitime_survit():
    # Le filtre porte sur la presence d'un mot, pas sur une longueur : couper
    # sous huit caracteres perdrait « Sapiens ».
    html = """
    <li>Harari Y. N. (2011). <cite><a class="external" href="https://example.org/s">Sapiens</a>.
    Harvill Secker.</cite></li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.title == "Sapiens"


def test_un_lien_de_service_ne_tient_pas_lieu_de_titre():
    html = """
    <li>Miller G. (1956). <cite class="citation journal">The magical number seven.
    <a class="external" href="https://web.archive.org/x">Archived</a> from the original</cite></li>
    """
    li = BeautifulSoup(html, "lxml").find("li")
    ref = _parse_reference_li(li)
    assert ref is not None
    assert ref.title is not None
    assert ref.title.lower() != "archived"
    assert "magical number seven" in ref.title
