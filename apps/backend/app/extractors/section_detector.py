"""Detection stricte de la section References dans le HTML d'une page.

Objectif : bornage explicite du DOM pour distinguer la bibliographie
citee par le contenu d'autres blocs de refs (Cited By, Related Articles,
Author Contributions, etc.). Toute ref candidate proposee par S2, le
scraping HTML brut ou le LLM DOIT etre trouvable dans la section bornee
sinon elle est droppee.

Fallback : si aucune section identifiable, la validation retombe sur le
body complet (moins precise, badge confidence=medium remonte a l'user).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from app.services.import_parsers import ImportedRef, _doi_from_url

# Selecteurs CSS pour attraper les sections References sur les principaux
# templates : Frontiers, PMC, Nature, arXiv, Wikipedia, Elsevier, Wiley,
# Springer, PLOS, blogs generiques avec class="references".
_SECTION_SELECTORS = [
    "section[id*='references' i]",
    "section[id*='bibliograph' i]",
    "div[id*='references' i]",
    "div[id*='bibliograph' i]",
    "section[class*='references' i]",
    "div[class*='references' i]",
    "div[class*='ref-list' i]",
    "ol[class*='references' i]",
    "ol[id*='references' i]",
    "ul[class*='references' i]",
    "section[data-title='References']",
]

# Headings a matcher en fallback quand le HTML ne porte pas de classe/id
# explicite. Multi-langue mais focus FR/EN.
_REFS_HEADING_RE = re.compile(
    r"^\s*(references?|bibliograph(?:y|ie)|works?\s+cited|sources?)\s*$",
    re.IGNORECASE,
)

# Ce qui vient APRES la section References et sert de borne de fin :
# ces headings ne font PAS partie de la biblio et doivent etre exclus.
_END_HEADING_RE = re.compile(
    r"^\s*("
    r"cited\s+by|"
    r"related\s+articles?|"
    r"see\s+also|"
    r"author\s+contributions?|"
    r"acknowledg[e]?ments?|"
    r"remerciements?|"
    r"funding|"
    r"financement|"
    r"conflict\s+of\s+interest|"
    r"conflit\s+d'?int.r.ts?|"
    r"data\s+availability|"
    r"disponibilit.\s+des\s+donn.es|"
    r"supplementary(?:\s+(?:material|data))?|"
    r"annexes?|"
    r"footnotes?|"
    r"notes?|"
    r"about\s+the\s+authors?"
    r")\s*$",
    re.IGNORECASE,
)


@dataclass
class SectionBoundary:
    """Resultat d'une detection de section References."""

    text: str  # texte complet borne (utilise pour les recherches)
    node_html: str  # le HTML de la section (utile debugging)
    method: str  # 'selector' | 'heading' | 'none'


def _text_of(node: Tag) -> str:
    """Extrait le texte visible d'un noeud BS4 en nettoyant scripts/styles."""
    for tag in node(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return node.get_text(" ", strip=True)


def _find_end_boundary(start: Tag) -> Tag | None:
    """Depuis un noeud start, trouve le premier sibling suivant qui marque
    la fin de la section References (heading Cited By, Author Contributions,
    etc. ou nouvelle section semantique).
    """
    for sibling in start.find_all_next():
        if sibling in start.descendants:
            continue
        if sibling.name in ("h1", "h2", "h3"):
            heading_text = sibling.get_text(" ", strip=True)
            if _END_HEADING_RE.match(heading_text):
                return sibling
        if sibling.name == "section" and sibling is not start:
            return sibling
    return None


def _bound_text_between(start: Tag, end: Tag | None) -> str:
    """Concatene le texte entre start et end (exclusif)."""
    if end is None:
        return _text_of(start)
    parts: list[str] = []
    parts.append(_text_of(start))
    for sibling in start.find_all_next():
        if sibling is end:
            break
        if sibling in start.descendants:
            continue
        if not isinstance(sibling, Tag):
            continue
        # Eviter de double-compter les descendants (find_all_next descend aussi)
        # -> on ne prend que les elements de plus haut niveau: si sibling est
        # descendant du precedent, skip.
        parts.append(sibling.get_text(" ", strip=True))
    return " ".join(p for p in parts if p)


def detect_references_section(html: str) -> SectionBoundary | None:
    """Detecte la section References dans le HTML. None si introuvable.

    Strategie en 2 temps :
      1. Selecteurs CSS semantiques (id/class references, bibliography, etc.)
      2. Fallback textuel sur headings h1/h2/h3 matchant 'References' /
         'Bibliographie' / 'Works Cited' / 'Sources'
    """
    soup = BeautifulSoup(html, "lxml")

    # 1. Selecteurs CSS
    for selector in _SECTION_SELECTORS:
        try:
            node = soup.select_one(selector)
        except Exception:  # selector CSS invalide sur certains DOMs
            continue
        if node is None:
            continue
        text = _text_of(node)
        if len(text) < 80:
            continue  # section trop courte -> probablement pas la bonne
        return SectionBoundary(text=text, node_html=str(node)[:5000], method="selector")

    # 2. Fallback heading
    for heading in soup.find_all(["h1", "h2", "h3"]):
        heading_text = heading.get_text(" ", strip=True)
        if not _REFS_HEADING_RE.match(heading_text):
            continue
        end = _find_end_boundary(heading)
        text = _bound_text_between(heading, end)
        if len(text) < 80:
            continue
        return SectionBoundary(text=text, node_html="", method="heading")

    return None


# ── Validation d'appartenance : la ref candidate est-elle citee ? ────────


def _norm_search(s: str) -> str:
    """Normalise pour recherche : lowercase, espaces multiples collapses,
    diacritiques ignores (approche simple, on garde les caracteres tels quels
    mais on compare sans casse)."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def _first_lastname(authors: str | None) -> str | None:
    """Extrait le nom de famille du premier auteur d'une chaine libre.

    Gere :
    - 'Family, G.'         -> 'Family'
    - 'Family G.'          -> 'Family'
    - 'G. Family'          -> 'Family'
    - 'Family1 G., Family2 H.' -> 'Family1'
    """
    if not authors:
        return None
    first = authors.split(",")[0].strip()
    if not first:
        return None
    parts = first.split()
    if not parts:
        return None
    # Cas 'G. Family' : initiales devant -> le dernier token est le nom
    # Cas 'Family G.' : premier token = nom
    if re.match(r"^[A-Z]\.$", parts[0]):
        return parts[-1]
    return parts[0]


def is_ref_in_section(ref: ImportedRef, section: SectionBoundary) -> bool:
    """Une ref est consideree comme presente si l'un de ces signaux match :
    - DOI ou URL exact present dans le texte borne (signal le plus fiable)
    - Titre long (>=5 mots signifiants) trouve a >=60% dans le texte borne
    - Titre court (<5 mots) OU absent : requiert (auteur principal + annee)
      dans le texte borne, motif "Lastname ... YYYY"

    La distinction long/court evite les faux positifs sur les titres
    generiques ("Neural correlates", "Response Inhibition") qui matchent
    trop facilement dans une section References de neuroscience.
    """
    haystack = _norm_search(section.text)

    # 1. DOI ou URL exact — signal le plus fiable, gagne toujours.
    doi = _doi_from_url(ref.url) if ref.url else None
    if doi and doi in haystack:
        return True
    if ref.url and ref.url.lower() in haystack:
        return True

    lastname = _first_lastname(ref.authors)
    lastname_lc = lastname.lower() if lastname else None

    # 2. Titre "long" (>=4 mots signifiants) : match 60% consecutif suffit.
    if ref.title:
        title_norm = _norm_search(ref.title)
        words = [w for w in re.findall(r"\w+", title_norm) if len(w) >= 4]
        if len(words) >= 4:
            window = max(3, int(len(words) * 0.6))
            for i in range(len(words) - window + 1):
                snippet = r"\W+".join(re.escape(w) for w in words[i : i + window])
                if re.search(snippet, haystack):
                    return True
        # Titre court (1-3 mots signifiants) : trop generique. Exige auteur+annee
        # en confirmation dans le texte borne. Evite les faux positifs sur
        # "Neural correlates", "Response Inhibition", etc.
        elif lastname_lc and ref.year and title_norm in haystack:
            pattern = rf"{re.escape(lastname_lc)}[^)]{{0,60}}\b{ref.year}\b"
            if re.search(pattern, haystack):
                return True

    # 3. Refs sans titre : auteur + annee reste possible (blogs, tweets)
    if not ref.title and lastname_lc and ref.year:
        pattern = rf"{re.escape(lastname_lc)}[^)]{{0,60}}\b{ref.year}\b"
        if re.search(pattern, haystack):
            return True

    return False


def is_ref_in_body(ref: ImportedRef, html: str) -> bool:
    """Meme logique que is_ref_in_section mais sur le body nettoye.

    Utilise en fallback quand aucune section References n'est detectable :
    on cherche des traces de citation dans <main> ou <article> ou <body>.
    Confidence remontee a l'user = 'medium'.
    """
    soup = BeautifulSoup(html, "lxml")
    root = soup.find("main") or soup.find("article") or soup.find("body") or soup
    if isinstance(root, Tag):
        for tag in root(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
            tag.decompose()
        text = root.get_text(" ", strip=True)
    else:
        text = str(root)
    pseudo_section = SectionBoundary(text=text, node_html="", method="body")
    return is_ref_in_section(ref, pseudo_section)
