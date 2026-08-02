from __future__ import annotations

import pytest

from app.services.content_identity import (
    escape_like,
    extract_doi,
    normalize_url,
    url_variants,
)


class TestExtractDoi:
    def test_reads_a_bare_doi(self):
        assert extract_doi("10.3389/fpsyg.2022.651547") == "10.3389/fpsyg.2022.651547"

    def test_reads_a_doi_buried_in_a_url(self):
        assert extract_doi("https://doi.org/10.1002/wps.21122") == "10.1002/wps.21122"

    def test_reads_a_doi_from_a_publisher_url(self):
        # Le « /full » de Frontiers designe une facon de lire l'article, pas un
        # autre article : garde, il empecherait de reconnaitre la reference
        # saisie avec le DOI nu sur la fiche qui la cite.
        url = "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.651547/full"
        assert extract_doi(url) == "10.3389/fpsyg.2022.651547"

    def test_strips_a_publisher_view_suffix(self):
        assert extract_doi("https://onlinelibrary.wiley.com/doi/10.1002/wps.21122/pdf") == (
            "10.1002/wps.21122"
        )

    def test_lowercases(self):
        # Un DOI est insensible a la casse : deux editeurs le publient
        # differemment, la meme reference doit se reconnaitre.
        assert extract_doi("10.1000/ABC.Def") == "10.1000/abc.def"

    def test_drops_sentence_punctuation(self):
        assert extract_doi("cf. 10.1002/wps.21122.") == "10.1002/wps.21122"

    def test_ignores_a_url_without_doi(self):
        assert extract_doi("https://www.nature.com/articles/d41586-022-00003-1") is None

    def test_ignores_empty(self):
        assert extract_doi(None) is None
        assert extract_doi("") is None


class TestNormalizeUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.nature.com/articles/abc/",
            "http://nature.com/articles/abc",
            "https://NATURE.com/articles/abc#section",
            "https://www.nature.com/articles/abc?utm_source=twitter",
        ],
    )
    def test_same_content_normalizes_identically(self, url):
        assert normalize_url(url) == "nature.com/articles/abc"

    def test_keeps_the_query_that_carries_the_identity(self):
        # Sur YouTube l'identite du contenu est dans la requete, pas le chemin.
        assert normalize_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == (
            "youtube.com/watch?v=dQw4w9WgXcQ"
        )

    def test_sorts_the_remaining_query(self):
        assert normalize_url("https://a.com/x?b=2&a=1") == normalize_url("https://a.com/x?a=1&b=2")

    def test_distinguishes_two_different_paths(self):
        assert normalize_url("https://a.com/x") != normalize_url("https://a.com/y")

    def test_ignores_a_string_without_host(self):
        assert normalize_url("pas une url") is None
        assert normalize_url(None) is None


class TestUrlVariants:
    def test_covers_the_common_writings(self):
        variants = url_variants("https://nature.com/articles/abc")
        for expected in (
            "https://nature.com/articles/abc",
            "http://nature.com/articles/abc",
            "https://www.nature.com/articles/abc",
            "https://nature.com/articles/abc/",
        ):
            assert expected in variants

    def test_omits_the_trailing_slash_when_a_query_is_present(self):
        variants = url_variants("https://youtube.com/watch?v=x")
        assert not any(v.endswith("/") for v in variants)

    def test_is_empty_on_a_non_url(self):
        assert url_variants("nope") == []


class TestEscapeLike:
    def test_neutralizes_sql_wildcards(self):
        # Un DOI peut contenir « _ », qui vaut « n'importe quel caractere » en
        # LIKE et elargirait silencieusement la correspondance.
        assert escape_like("10.1000/a_b%c") == r"10.1000/a\_b\%c"
