"""Tests scoring syntaxique universel."""

from __future__ import annotations

from app.extractors.ref_scorer import should_drop, syntactic_score
from app.services.import_parsers import ImportedRef


def _ref(url="", title=None) -> ImportedRef:
    return ImportedRef(url=url, title=title)


def test_empty_ref_drop():
    assert syntactic_score(_ref()) == 0.0
    assert should_drop(_ref()) is True


def test_url_only_no_title_ok():
    r = _ref(url="https://example.com", title=None)
    assert syntactic_score(r) >= 0.5
    assert should_drop(r) is False


def test_pure_number_drop():
    r = _ref(url="https://example.com", title="12")
    assert should_drop(r) is True


def test_short_citation_fragment_drop():
    r = _ref(url="https://example.com", title="[12] p. 45")
    assert should_drop(r) is True


def test_legit_short_book_title_kept():
    # 1984 (Orwell), Dune (Herbert), Sapiens (Harari) : titres legitimes courts
    assert should_drop(_ref(url="", title="Sapiens")) is False
    assert should_drop(_ref(url="", title="Dune")) is False
    # "1984" est un cas ambigu (pur nombre). On droppe car indistinguable
    # d'un fragment de numero de citation. Trade-off assume : mieux vaut
    # perdre le titre Orwell (rare) que garder tous les "[12]" fragments.


def test_open_tail_drop():
    assert should_drop(_ref(url="", title="Development of-")) is True
    assert should_drop(_ref(url="", title="A Study on (")) is True


def test_duplicate_word_run():
    r = _ref(url="", title="Frontiers in Neural Circuits Neural Circuits")
    assert should_drop(r) is True


def test_normal_scientific_title_kept():
    r = _ref(
        url="https://doi.org/10.1/abc",
        title="A Developmental fMRI Study of the Stroop Color-Word Task",
    )
    assert syntactic_score(r) == 1.0
    assert should_drop(r) is False


def test_normal_book_title_kept():
    assert should_drop(_ref(url="", title="Surveiller et punir")) is False
    assert should_drop(_ref(url="", title="A brief history of time")) is False


def test_reportage_no_year_no_id_kept():
    # Un reportage sans date connue et sans DOI/ISBN : signal 1 le juge
    # uniquement sur le titre. Pas de penalite pour year/id absent.
    r = _ref(
        url="https://example.tv/reportage/foo",
        title="Enquête sur les algorithmes de recommandation",
    )
    assert should_drop(r) is False
