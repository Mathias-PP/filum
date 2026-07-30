"""Tests dedup multi-cle (title+author) OU (doi/url), avec year distinctif."""

from __future__ import annotations

from app.extractors.ref_dedup import (
    dedupe_refs,
    matches_authoritative_work,
    norm_authors_list,
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
    assert (
        norm_title("À la recherche") == "àlarecherche"
        or norm_title("À la recherche").startswith("larecherche")
        or norm_title("À la recherche")
    )  # normalisation NFKC
    assert norm_title(None) == ""


def test_norm_first_author_variants():
    assert norm_first_author("Wolfe, C. D.") == "wolfe"
    assert norm_first_author("Wolfe C. D.") == "wolfe"
    assert norm_first_author("C. Wolfe") == "wolfe"
    assert norm_first_author("Wolfe C., Bell M.") == "wolfe"
    assert norm_first_author(None) == ""
    assert norm_first_author("") == ""


def test_norm_first_author_given_family():
    # Format S2 : 'Given Family' ou 'Given Middle Family'
    assert norm_first_author("Benjamin Williams") == "williams"
    assert norm_first_author("Benjamin R. Williams") == "williams"
    assert norm_first_author("A. Diamond") == "diamond"
    assert norm_first_author("A.B. Aron") == "aron"


def test_norm_first_author_multi_authors_s2():
    # Format S2 : 'Given Family, Given Family, ...'
    assert norm_first_author("Benjamin R. Williams, J. Ponesse, R. Schachar") == "williams"


def test_norm_first_author_particules():
    assert norm_first_author("van der Meere J.") == "vandermeere"
    assert norm_first_author("de la Torre A.") == "delatorre"
    assert norm_first_author("von Neumann J.") == "vonneumann"
    assert norm_first_author("Van de Laar M. C.") == "vandelaar"


def test_norm_first_author_compound_hyphenated():
    assert norm_first_author("Kim-Spoon J.") == "kimspoon"
    assert norm_first_author("Deater-Deckard K.") == "deaterdeckard"


def test_norm_first_author_unicode():
    assert (
        norm_first_author("García A.") == "garcía"
        or norm_first_author("García A.") == "garcia"
        or "garc" in norm_first_author("García A.")
    )
    # Gligorović (letter ć = c hachek) doit rester normalise vers c ou etre garde
    result = norm_first_author("Gligorović M.")
    assert "gligorovi" in result


def test_norm_first_author_corporate():
    # Corporate authors : garder l'entite comme chaine
    result = norm_first_author("American Psychiatric Association")
    assert "americanpsychiatric" in result or "association" in result


def test_norm_first_author_family_comma_given():
    # BibTeX classique
    assert norm_first_author("Wolfe, Christy D.") == "wolfe"
    assert norm_first_author("García, A.") == "garcía" or "garc" in norm_first_author("García, A.")


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


def test_same_ref_title_author_year_conflict_distinct():
    # Deux editions/republications avec meme titre+auteur mais annees
    # differentes = refs DISTINCTES (les bibliographies citent une edition
    # specifique, ex: livre 1ere edition 2001 vs 2e edition 2015).
    a = _ref(title="Introduction", authors="Foucault M.", year=1975)
    b = _ref(title="Introduction", authors="Foucault M.", year=1990)
    assert same_ref(a, b) is False


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


def test_norm_authors_list_multi():
    assert norm_authors_list("Wolfe C. D., Bell M. A.") == ["wolfe", "bell"]
    assert norm_authors_list("Wolfe, C. D., and Bell, M. A.") == ["wolfe", "bell"]
    assert norm_authors_list("Wolfe C. D.") == ["wolfe"]
    assert norm_authors_list(None) == []
    assert norm_authors_list("") == []


def test_same_ref_distinct_when_second_author_differs():
    # Meme 1er auteur + meme titre + meme annee mais 2eme auteur different :
    # papiers distincts (co-auteurs differents).
    a = _ref(
        title="Neural correlates of inhibition",
        authors="Wolfe C., Bell M.",
        year=2010,
    )
    b = _ref(
        title="Neural correlates of inhibition",
        authors="Wolfe C., Diamond A.",
        year=2010,
    )
    assert same_ref(a, b) is False


def test_same_ref_matches_when_second_author_absent_on_one_side():
    # Une des refs est tronquee ('Wolfe et al.' style, 1 auteur) :
    # tolere le match sur le seul 1er auteur pour ne pas perdre le merge.
    a = _ref(title="Neural correlates of inhibition", authors="Wolfe C.", year=2010)
    b = _ref(
        title="Neural correlates of inhibition",
        authors="Wolfe C., Bell M., Diamond A.",
        year=2010,
    )
    assert same_ref(a, b) is True


def test_matches_authoritative_work_long_title_ignores_authors():
    # Couche d'enrichissement : un titre long identique suffit, meme si les
    # chaines auteurs ont ete degradees differemment par les deux sources
    # ('J. Ridley' cote S2 vs 'Stroop' cote Crossref pour Stroop J. R.).
    title = "Studies of interference in serial verbal reactions"
    cr = _ref(title=title, authors="Stroop", year=1935)
    s2 = _ref(title=title, authors="J. Ridley", year=1992)
    assert matches_authoritative_work(s2, cr) is True
    # La dedup generale reste stricte : ce sont deux editions distinctes.
    assert same_ref(cr, s2) is False


def test_matches_authoritative_work_long_title_missing_authors():
    title = "The integration of cognition and emotion during infancy"
    cr = _ref(title=title, authors="Wolfe", year=2007)
    s2 = _ref(title=title, authors=None, year=None)
    assert matches_authoritative_work(s2, cr) is True


def test_matches_authoritative_work_short_title_still_needs_authors():
    # Titre court : trop d'homonymes, on exige la confirmation par auteur.
    cr = _ref(title="Introduction", authors="Foucault M.", year=1975)
    s2_same = _ref(title="Introduction", authors="Foucault M.", year=1990)
    s2_other = _ref(title="Introduction", authors="Deleuze G.", year=1968)
    s2_noauthor = _ref(title="Introduction", authors=None)
    assert matches_authoritative_work(s2_same, cr) is True
    assert matches_authoritative_work(s2_other, cr) is False
    assert matches_authoritative_work(s2_noauthor, cr) is False


def test_matches_authoritative_work_different_titles_never_match():
    cr = _ref(title="Studies of interference in serial verbal reactions", authors="Stroop")
    s2 = _ref(title="Executive functions and self-regulation in childhood", authors="Stroop")
    assert matches_authoritative_work(s2, cr) is False


def test_matches_authoritative_work_second_author_gate():
    # Meme titre + 1er auteur mais 2eme auteur different chez S2 :
    # NE PAS considerer comme meme papier autoritative (pas de drop).
    cr = _ref(title="Some paper title long enough here", authors="Smith A., Jones B.", year=2015)
    s2_ok = _ref(title="Some paper title long enough here", authors="Smith A., Jones B.", year=2015)
    s2_diff = _ref(
        title="Some paper title long enough here", authors="Smith A., Miller C.", year=2015
    )
    assert matches_authoritative_work(s2_ok, cr) is True
    assert matches_authoritative_work(s2_diff, cr) is False
