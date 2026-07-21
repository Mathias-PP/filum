"""Tests unitaires purs de l'extraction de section References.

Isolent l'heuristique (_extract_references_text) du reste de l'endpoint :
pas de HTTP client, pas d'auth, pas de LLM. Verifient le comportement sur
les 4 cas critiques : section dediee trouvee, script/style ignores,
fallback body nettoye du chrome UI, section trop petite ignoree.
"""

from __future__ import annotations

from app.api.v1.endpoints.imports import _extract_references_text


def test_extracts_dedicated_references_section():
    html = """
    <html><body>
      <article>main text</article>
      <section id="references">
        <h2>References</h2>
        <ol>
          <li>Ref A: Doe J. Learning. https://doi.org/10.1/a</li>
          <li>Ref B: Roe M. Memory. https://doi.org/10.1/b</li>
          <li>Ref C: Poe A. Attention. https://doi.org/10.1/c</li>
        </ol>
      </section>
    </body></html>
    """
    text, found = _extract_references_text(html)
    assert found is True
    assert "Ref A" in text and "Ref C" in text
    assert "main text" not in text  # scope limite a la section


def test_script_and_style_stripped_even_inside_refs_section():
    """JS et CSS embarques dans la section References doivent disparaitre."""
    html = """
    <html><body>
      <section id="references">
        <h2>References</h2>
        <ol>
          <li>Kahneman D, Tversky A. Prospect theory. https://doi.org/10.1/a</li>
          <li>Baddeley A. Working memory. https://doi.org/10.1/b</li>
          <li>Damasio A. Descartes' error. https://doi.org/10.1/c</li>
        </ol>
        <script>var trackingBloat = 'x'.repeat(500);</script>
        <style>.ref-list { color: red; }</style>
      </section>
    </body></html>
    """
    text, found = _extract_references_text(html)
    assert found is True
    assert "trackingBloat" not in text
    assert "color: red" not in text
    assert "Kahneman" in text


def test_fallback_body_strips_ui_chrome():
    """Sans section References dediee, on retire nav/header/footer/aside."""
    html = """
    <html><body>
      <header><nav>Menu | Logo | Search</nav></header>
      <aside>Ads and related links</aside>
      <main>
        <p>Article body with important content.</p>
        <p>See https://doi.org/10.1/a for details.</p>
      </main>
      <footer>Copyright 2026</footer>
      <script>window.tracker.init();</script>
    </body></html>
    """
    text, found = _extract_references_text(html)
    assert found is False
    assert "important content" in text
    assert "Menu" not in text
    assert "Copyright" not in text
    assert "tracker.init" not in text


def test_short_references_section_falls_through():
    """Une section 'References' qui contient <80 chars est ignoree
    (souvent un placeholder vide de theme)."""
    html = """
    <html><body>
      <section id="references"><h2>References</h2></section>
      <main>
        <p>Real content with reference https://doi.org/10.1/a</p>
      </main>
    </body></html>
    """
    text, found = _extract_references_text(html)
    assert found is False
    assert "Real content" in text


def test_various_selectors_matched():
    """Verifie que quelques selecteurs alternatifs marchent
    (Nature/PMC/scholarly)."""
    for html in [
        "<html><body><div id='references'>"
        + "<p>Ref A https://doi.org/10.1/a</p>" * 5
        + "</div></body></html>",
        "<html><body><ol class='references'>"
        + "<li>Ref A https://doi.org/10.1/a</li>" * 5
        + "</ol></body></html>",
        "<html><body><div class='ref-list'>"
        + "<p>Ref A https://doi.org/10.1/a</p>" * 5
        + "</div></body></html>",
    ]:
        text, found = _extract_references_text(html)
        assert found is True, f"selector should have matched in: {html[:80]}"
        assert "Ref A" in text


def test_caps_output_at_max_length():
    html = "<html><body><section id='references'>" + ("Ref x " * 20000) + "</section></body></html>"
    text, found = _extract_references_text(html)
    assert found is True
    assert len(text) <= 60_000


# --- Conversion S2 -> ImportedRef : exhaustivite des refs sans DOI ----------


def test_s2_ref_without_url_kept_with_title_only():
    from app.api.v1.endpoints.imports import _s2_ref_to_imported_ref
    from app.extractors.semantic_scholar import SemanticScholarRef

    ref = _s2_ref_to_imported_ref(SemanticScholarRef(title="Un livre sans DOI ni auteurs S2"))
    assert ref is not None
    assert ref.url == ""
    assert ref.title == "Un livre sans DOI ni auteurs S2"


def test_s2_ref_without_url_nor_title_dropped():
    from app.api.v1.endpoints.imports import _s2_ref_to_imported_ref
    from app.extractors.semantic_scholar import SemanticScholarRef

    assert _s2_ref_to_imported_ref(SemanticScholarRef(authors="X Y.", year=1999)) is None


def test_merge_s2_refs_adds_no_url_refs():
    from app.api.v1.endpoints.imports import _merge_s2_refs
    from app.extractors.semantic_scholar import SemanticScholarRef
    from app.services.import_parsers import ParseResult

    s2_refs = [
        SemanticScholarRef(title="Paper A", doi="10.1/a", url="https://doi.org/10.1/a"),
        SemanticScholarRef(title="Livre B", authors="Auteur B."),
        SemanticScholarRef(title="Livre C"),
    ]
    result = _merge_s2_refs(ParseResult(), s2_refs)
    assert len(result.refs) == 3
    assert result.skipped == 0


def test_crossref_reference_item_parsing():
    from app.extractors.url_extractor import _crossref_reference_item_to_ref

    # Article avec DOI
    ref = _crossref_reference_item_to_ref(
        {"DOI": "10.1080/13854049608406663", "article-title": "Tower of London", "year": "1996"}
    )
    assert ref.doi == "10.1080/13854049608406663"
    assert ref.url == "https://doi.org/10.1080/13854049608406663"
    assert ref.year == 1996

    # Livre Elsevier : titre dans series-title, pas de DOI
    book = _crossref_reference_item_to_ref(
        {"series-title": "Working memory", "author": "Baddeley", "year": "1986"}
    )
    assert book.title == "Working memory"
    assert book.url is None
    assert book.authors == "Baddeley"

    # Annee illisible -> None, pas d'exception
    weird = _crossref_reference_item_to_ref({"unstructured": "Some ref", "year": "n.d."})
    assert weird.year is None
    assert weird.title == "Some ref"
