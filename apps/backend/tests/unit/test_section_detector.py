"""Tests section-detection (BS4 DOM navigation) et validation d'appartenance."""

from __future__ import annotations

from app.extractors.section_detector import (
    detect_references_section,
    is_ref_in_body,
    is_ref_in_section,
)
from app.services.import_parsers import ImportedRef


def test_detect_via_section_id():
    html = """
    <html><body>
    <main>
    <section id="references">
      <h2>References</h2>
      <p>Wolfe C. D., Bell M. A. (2007). The integration of cognition and emotion. Brain Cogn 65, 3–13. doi:10.1016/j.bandc.2006.01.009</p>
      <p>Adleman N. E. et al. (2002). A Developmental fMRI Study. NeuroImage 16, 61–75.</p>
    </section>
    <section id="cited-by"><h2>Cited By</h2><p>Foreign paper we should NOT include</p></section>
    </main>
    </body></html>
    """
    result = detect_references_section(html)
    assert result is not None
    assert result.method == "selector"
    assert "Wolfe" in result.text
    assert "Adleman" in result.text
    # cited-by hors bornage : selecteur section#references match uniquement le noeud lui-meme
    assert "Foreign paper" not in result.text


def test_detect_via_heading_fallback():
    html = """
    <html><body>
    <article>
    <p>Main content here</p>
    <h2>References</h2>
    <p>Smith J. (2020). A study. Journal 5, 1-10.</p>
    <p>Jones K. (2019). Another one. Journal 6, 11-20.</p>
    <h2>Author Contributions</h2>
    <p>SJ wrote the paper. KJ analyzed data.</p>
    </article>
    </body></html>
    """
    result = detect_references_section(html)
    assert result is not None
    assert result.method == "heading"
    assert "Smith J." in result.text
    assert "Jones K." in result.text
    # bornage sur "Author Contributions" heading
    assert "SJ wrote" not in result.text


def test_detect_returns_none_when_no_section():
    html = "<html><body><p>Just a paragraph.</p></body></html>"
    assert detect_references_section(html) is None


def test_is_ref_in_section_by_doi():
    from app.extractors.section_detector import SectionBoundary

    section = SectionBoundary(
        text="Wolfe C. D. 2007. doi:10.1016/j.bandc.2006.01.009",
        node_html="",
        method="test",
    )
    ref = ImportedRef(url="https://doi.org/10.1016/j.bandc.2006.01.009", title="Some")
    assert is_ref_in_section(ref, section) is True


def test_is_ref_in_section_by_title_60_percent():
    from app.extractors.section_detector import SectionBoundary

    section = SectionBoundary(
        text="Adleman NE et al 2002 A Developmental fMRI Study of the Stroop Color-Word Task",
        node_html="",
        method="test",
    )
    ref = ImportedRef(
        url="",
        title="A Developmental fMRI Study of the Stroop Task",  # 6 mots >=4 sur 8, partiel
    )
    assert is_ref_in_section(ref, section) is True


def test_is_ref_in_section_not_found():
    from app.extractors.section_detector import SectionBoundary

    section = SectionBoundary(
        text="Wolfe 2007 memory development",
        node_html="",
        method="test",
    )
    # papier abeilles hors sujet
    ref = ImportedRef(
        url="https://doi.org/10.1000/nowhere",
        title="Molecular analyses of bee foraging distance",
        authors="Smith J.",
        year=2015,
    )
    assert is_ref_in_section(ref, section) is False


def test_is_ref_in_body_fallback():
    html = """
    <html><body>
    <main>
    <p>As shown by Wolfe (2007), memory development is complex.</p>
    <p>See also Smith 2015 on this topic.</p>
    </main>
    </body></html>
    """
    ref = ImportedRef(url="", title=None, authors="Wolfe C.", year=2007)
    assert is_ref_in_body(ref, html) is True

    ref_missing = ImportedRef(url="", title=None, authors="Foucault M.", year=1975)
    assert is_ref_in_body(ref_missing, html) is False
