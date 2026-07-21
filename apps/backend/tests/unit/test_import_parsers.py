from __future__ import annotations

import io
import json
import zipfile
import zlib

from app.services.import_parsers import (
    detect_format,
    parse_bibtex,
    parse_csl_json,
    parse_docx,
    parse_file,
    parse_html,
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


# --- DOCX --------------------------------------------------------------------


def _make_docx(document_xml: str, rels_xml: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", document_xml)
        if rels_xml is not None:
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
    return buf.getvalue()


DOCX_DOCUMENT = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Bibliographie</w:t></w:r></w:p>
    <w:p><w:r><w:t>Dupont (2024). Memoire. doi: 10.1234/docx.567</w:t></w:r></w:p>
    <w:p><w:r><w:t>Voir https://example.org/docx-source pour le detail.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

DOCX_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.org/lien-docx" TargetMode="External"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def test_parse_docx():
    data = _make_docx(DOCX_DOCUMENT, DOCX_RELS)
    result = parse_docx(data)
    urls = [r.url for r in result.refs]
    assert "https://doi.org/10.1234/docx.567" in urls
    assert "https://example.org/docx-source" in urls
    # Les hyperliens Word vivent dans les relationships, pas dans le texte.
    assert "https://example.org/lien-docx" in urls


def test_parse_docx_invalid_zip():
    result = parse_docx(b"pas un zip du tout")
    assert result.refs == []


def test_detect_format_docx_and_html():
    docx = _make_docx(DOCX_DOCUMENT)
    assert detect_format("biblio.docx", b"") == "docx"
    assert detect_format(None, docx) == "docx"
    assert detect_format("page.html", b"") == "html"
    assert detect_format("page.htm", b"") == "html"
    assert detect_format(None, b"<!DOCTYPE html><html><body>x</body></html>") == "html"
    # Un zip quelconque sans word/document.xml n'est pas un docx.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("autre.txt", "x")
    assert detect_format(None, buf.getvalue()) == "markdown"


# --- HTML (page sauvegardee) -------------------------------------------------

HTML_SAMPLE = """<!DOCTYPE html>
<html><head><title>Ma page</title><style>a { color: red; }</style></head>
<body>
  <nav><a href="https://example.org/">Accueil</a></nav>
  <h2>References</h2>
  <ul>
    <li><a href="https://doi.org/10.5555/html.1">Un article fondateur</a></li>
    <li><a href="https://example.org/rapport">Rapport 2024</a></li>
    <li>Martin (2023). Sans lien mais avec DOI 10.5555/html.2 dans le texte.</li>
  </ul>
  <script>var x = "https://tracker.example.com/js";</script>
</body></html>
"""


def test_parse_html():
    result = parse_html(HTML_SAMPLE.encode())
    by_url = {r.url: r for r in result.refs}
    assert "https://doi.org/10.5555/html.1" in by_url
    assert by_url["https://doi.org/10.5555/html.1"].title == "Un article fondateur"
    assert "https://example.org/rapport" in by_url
    assert "https://doi.org/10.5555/html.2" in by_url
    # Les URLs dans les <script>/<style> ne sont pas des sources.
    assert "https://tracker.example.com/js" not in by_url


def test_parse_file_dispatch_docx_and_html():
    docx = _make_docx(DOCX_DOCUMENT)
    result = parse_file("refs.docx", docx)
    assert any(r.url == "https://doi.org/10.1234/docx.567" for r in result.refs)
    result = parse_file("page.html", HTML_SAMPLE.encode())
    assert any(r.url == "https://example.org/rapport" for r in result.refs)
