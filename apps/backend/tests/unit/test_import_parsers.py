from __future__ import annotations

import json
import zlib

from app.services.import_parsers import (
    detect_format,
    parse_bibtex,
    parse_csl_json,
    parse_file,
    parse_markdown,
    parse_pdf,
)

BIBTEX_SAMPLE = """
@article{dupont2024,
  title = {Memoire et plasticite {cerebrale}},
  author = {Dupont, Marie and Martin, Jean},
  year = {2024},
  doi = {10.1234/abcd.5678},
}

@book{kandel2021,
  title = "Principles of Neural Science",
  author = "Kandel, Eric",
  year = 2021,
  url = {https://example.org/kandel},
}

@misc{nourl2020,
  title = {Entree sans URL ni DOI},
  year = {2020},
}

@comment{ceci est ignore}
"""


def test_parse_bibtex():
    result = parse_bibtex(BIBTEX_SAMPLE)
    assert result.skipped == 1
    assert len(result.refs) == 2
    art = result.refs[0]
    assert art.url == "https://doi.org/10.1234/abcd.5678"
    assert art.title == "Memoire et plasticite cerebrale"
    assert art.authors == "Dupont, Marie, Martin, Jean"
    assert art.year == 2024
    assert art.category == "article-scientifique"
    book = result.refs[1]
    assert book.url == "https://example.org/kandel"
    assert book.category == "livre"
    assert book.year == 2021


def test_parse_csl_json_zotero():
    items = [
        {
            "type": "article-journal",
            "title": "Sleep and memory",
            "author": [{"family": "Walker", "given": "Matthew"}],
            "issued": {"date-parts": [[2019, 5]]},
            "DOI": "10.5555/sleep.42",
        },
        {
            "type": "webpage",
            "title": "Une page",
            "URL": "https://example.org/page",
        },
        {"type": "book", "title": "Sans lien"},
    ]
    result = parse_csl_json(json.dumps(items))
    assert result.skipped == 1
    assert len(result.refs) == 2
    assert result.refs[0].url == "https://doi.org/10.5555/sleep.42"
    assert result.refs[0].authors == "Walker Matthew"
    assert result.refs[0].year == 2019
    assert result.refs[0].category == "article-scientifique"
    assert result.refs[1].category == "page-web"


def test_parse_csl_json_invalid():
    assert parse_csl_json("not json").refs == []
    assert parse_csl_json('{"items": "nope"}').refs == []


def test_parse_markdown_obsidian():
    text = (
        "# Notes\n"
        "Voir [cet article](https://example.org/article) et aussi\n"
        "https://example.org/nu.\n"
        "DOI: 10.9999/xyz.123\n"
        "![image](https://example.org/img.png)\n"
    )
    result = parse_markdown(text)
    urls = [r.url for r in result.refs]
    assert "https://example.org/article" in urls
    assert "https://example.org/nu" in urls
    assert "https://doi.org/10.9999/xyz.123" in urls
    assert "https://example.org/img.png" not in urls
    assert result.refs[0].title == "cet article"


def test_parse_pdf_flate_stream():
    payload = b"Voir https://example.org/papier et doi 10.1111/pdf.99 fin"
    compressed = zlib.compress(payload)
    pdf = b"%PDF-1.4\nstream\n" + compressed + b"\nendstream\ntrailer"
    result = parse_pdf(pdf)
    urls = [r.url for r in result.refs]
    assert "https://example.org/papier" in urls
    assert "https://doi.org/10.1111/pdf.99" in urls


def test_detect_format():
    assert detect_format("refs.bib", b"") == "bibtex"
    assert detect_format("export.json", b"") == "csl-json"
    assert detect_format("notes.md", b"") == "markdown"
    assert detect_format("paper.pdf", b"") == "pdf"
    assert detect_format(None, b"%PDF-1.7 blah") == "pdf"
    assert detect_format(None, b'[{"type": "book"}]') == "csl-json"
    assert detect_format(None, b"@article{x, title={t}}") == "bibtex"
    assert detect_format(None, b"just some text") == "markdown"


def test_parse_file_dispatch():
    result = parse_file("refs.bib", BIBTEX_SAMPLE.encode())
    assert len(result.refs) == 2
    result = parse_file(None, b"https://example.org/x-longue-url")
    assert result.refs[0].url == "https://example.org/x-longue-url"


def test_dedupe_collapses_doi_and_publisher_url():
    """Frontiers canonical URL et l'URL doi.org du même DOI = même ref."""
    text = (
        "Une biblio :\n"
        "- https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.01561/full\n"
        "- https://doi.org/10.3389/fpsyg.2018.01561\n"
    )
    result = parse_markdown(text)
    # Sans le fix : 2 entrées (clés URL différentes). Avec le fix : 1 seule
    # entrée (clé canonique doi:10.3389/fpsyg.2018.01561).
    assert len(result.refs) == 1


def test_dedupe_key_extraction_from_various_publishers():
    from app.services.import_parsers import _dedupe_key

    frontiers = "https://www.frontiersin.org/articles/10.3389/fpsyg.2018.01561/full"
    doi_org = "https://doi.org/10.3389/fpsyg.2018.01561"
    wiley = "https://onlinelibrary.wiley.com/doi/full/10.1002/hbm.12345"
    assert _dedupe_key(frontiers) == _dedupe_key(doi_org)
    assert _dedupe_key(wiley).startswith("doi:10.1002/hbm.12345")
    # URL sans DOI reste identifiée par sa forme normalisée.
    assert _dedupe_key("https://example.org/article/") == "https://example.org/article"
