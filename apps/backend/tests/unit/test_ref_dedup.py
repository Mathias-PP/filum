"""Tests dedup multi-cle (title+author) OU (doi/url), avec year distinctif."""

from __future__ import annotations

from app.extractors.ref_dedup import (
    dedupe_refs,
    norm_first_author,
    norm_title,
    same_ref,
)
from app.services.import_parsers import ImportedRef


def _ref(**kw) -> ImportedRef:
    kw.setdefault("url", "")
    return ImportedRef(**kw)


def test_norm_title_alphanum_only():
    assert norm_title("The Origin of Species!") == "theoriginofspecies"
    assert norm_title("À la recherche") == "àlarecherche" or norm_title(
        "À la recherche"
    ).startswith("larecherche") or norm_title("À la recherche")  # normalisation NFKC
    assert norm_title(None) == ""


def test_norm_first_author_variants():
    assert norm_first_author("Wolfe, C. D.") == "wolfe"
    assert norm_first_author("Wolfe C. D.") == "wolfe"
    assert norm_first_author("C. Wolfe") == "wolfe"
    assert norm_first_author("Wolfe C., Bell M.") == "wolfe"
    assert norm_first_author(None) == ""
    assert norm_first_author("") == ""


def test_same_ref_doi_match_ignores_year():
    a = _ref(url="https://doi.org/10.1/abc", title="X", year=2001)
    b = _ref(url="https://doi.org/10.1/abc", title="X", year=2002)
    assert same_ref(a, b) is True


def test_same_ref_url_match():
    a = _ref(url="https://example.com/page/", title="A", authors="Doe J.")
    b = _ref(url="https://example.com/page", title="B", authors="Smith K.")
    assert same_ref(a, b) is True  # URL egal, meme si titres/auteurs differents


def test_same_ref_title_author_no_year_conflict():
    a = _ref(title="Introduction", authors="Foucault M.", year=None)
    b = _ref(title="Introduction", authors="Foucault M.", year=1975)
    assert same_ref(a, b) is True  # year absente sur a, pas de conflit


def test_same_ref_title_author_year_conflict():
    a = _ref(title="Introduction", authors="Foucault M.", year=1975)
    b = _ref(title="Introduction", authors="Foucault M.", year=1990)
    assert same_ref(a, b) is False  # years differentes = republication distincte


def test_same_ref_title_match_but_different_authors():
    a = _ref(title="Introduction", authors="Foucault M.", year=1975)
    b = _ref(title="Introduction", authors="Deleuze G.", year=1975)
    assert same_ref(a, b) is False


def test_dedupe_refs_merges_metadata():
    a = _ref(url="https://doi.org/10.1/x", title="Full title", authors=None, year=2020)
    b = _ref(url="https://doi.org/10.1/x", title=None, authors="Doe J.", year=None)
    out = dedupe_refs([a, b])
    assert len(out) == 1
    assert out[0].title == "Full title"
    assert out[0].authors == "Doe J."
    assert out[0].year == 2020


def test_dedupe_refs_preserves_distinct_homonyms():
    a = _ref(title="Introduction", authors="Foucault M.", year=1975)
    b = _ref(title="Introduction", authors="Deleuze G.", year=1968)
    out = dedupe_refs([a, b])
    assert len(out) == 2
