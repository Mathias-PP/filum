"""Oracle Wikipedia : recupere la biblio structuree d'une page via l'API
MediaWiki. Court-circuit les etages Crossref/S2/HTML/LLM quand ca marche.

Wikipedia expose la biblio dans un DOM stable : <ol class="references"> avec
un <li> par ref, contenant souvent <cite> + liens DOI/PMC/PubMed. Chaque
<li> est une source citee par l'article, donc pas de risque de mixage avec
"cited by" / "related" (Wikipedia ne les a pas).

API endpoint : GET https://{lang}.wikipedia.org/w/api.php
Parametres : action=parse&page={title}&prop=text&format=json&formatversion=2
Retour : {parse: {text: "<HTML fragment>"}} ou None si page absente.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.import_parsers import ImportedRef

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
_TIMEOUT = 10.0

_WIKIPEDIA_HOST_RE = re.compile(r"^([a-z]{2,3})\.wikipedia\.org$", re.IGNORECASE)


def is_wikipedia_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return bool(_WIKIPEDIA_HOST_RE.match(host))


def _extract_lang_and_title(url: str) -> tuple[str, str] | None:
    """Extrait (lang, page_title) depuis une URL Wikipedia. None si invalide."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    m = _WIKIPEDIA_HOST_RE.match(host)
    if not m:
        return None
    lang = m.group(1).lower()
    path = unquote(parsed.path or "")
    # Format : /wiki/Page_Title
    match_path = re.match(r"^/wiki/([^/#?]+)/?$", path)
    if not match_path:
        return None
    title = match_path.group(1).replace("_", " ")
    return lang, title


def _first_year_in(text: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def _parse_reference_li(li: Tag) -> ImportedRef | None:
    """Convertit un <li> de reference Wikipedia en ImportedRef.

    Strategie :
    - URL : premier lien DOI, sinon PMC, sinon PubMed, sinon premier
      lien externe. Sans URL -> ref conservee avec url='' si titre present.
    - Titre : premier <cite> ou premier lien externe, sinon extrait du
      texte brut (avant le premier point/annee).
    - Authors : partie avant le premier '(YYYY)' dans le texte.
    - Year : premier motif annee dans le texte.
    """
    text = li.get_text(" ", strip=True)
    # Wikipedia prefixe souvent par '^' ou '^ a b' (back-refs) : on nettoie.
    text = re.sub(r"^\s*\^\s*(?:[a-z]\s+)*", "", text)

    # 1. URL : DOI > PMC > PubMed > premier lien
    url = ""
    for a in li.select('a[href*="doi.org"]'):
        href = str(a.get("href") or "")
        if href:
            url = href
            break
    if not url:
        for a in li.select('a[href*="ncbi.nlm.nih.gov"]'):
            href = str(a.get("href") or "")
            if href:
                url = href
                break
    if not url:
        for a in li.select("a.external"):
            href = str(a.get("href") or "")
            if href and href.startswith(("http://", "https://")):
                url = href
                break

    # 2. Titre : premier <cite> ou premier lien avec du texte utile
    title = None
    cite = li.find("cite")
    if cite and isinstance(cite, Tag):
        # Wikipedia met souvent le titre dans un <a> a l'interieur du <cite>
        title_a = cite.find("a")
        title = title_a.get_text(" ", strip=True) if title_a else cite.get_text(" ", strip=True)
    if not title:
        for a in li.select("a.external"):
            text_a = a.get_text(" ", strip=True)
            if len(text_a) >= 8 and not text_a.startswith("10."):
                title = text_a
                break

    if title:
        title = title.strip('"“”').strip()

    # 3. Authors : partie avant '(YYYY)'
    authors = None
    m = re.match(r"^([^()]{3,120})\((?:19|20)\d{2}\)", text)
    if m:
        authors = m.group(1).strip(" ,.")

    year = _first_year_in(text)

    if not url and not title:
        return None

    return ImportedRef(
        url=url,
        title=title,
        authors=authors,
        year=year,
        category="page-web",
        raw_text=text[:500],
    )


async def fetch_wikipedia_references(url: str) -> list[ImportedRef] | None:
    """Recupere les refs de la page Wikipedia via l'API MediaWiki.

    Retourne None si :
    - l'URL n'est pas une page Wikipedia
    - l'API renvoie une erreur
    - aucune reference n'est trouvee (page tres courte, redirection, etc.)
    """
    parsed = _extract_lang_and_title(url)
    if not parsed:
        return None
    lang, title = parsed

    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    }
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(api_url, params=params)
        if r.status_code != 200:
            logger.warning("Wikipedia API %s returned %s", api_url, r.status_code)
            return None
        data = r.json()
    except Exception as e:
        logger.warning("Wikipedia API fetch failed for %s: %s", url, e)
        return None

    parse_block = data.get("parse") or {}
    html_text = parse_block.get("text")
    if not html_text or not isinstance(html_text, str):
        return None

    soup = BeautifulSoup(html_text, "lxml")
    reflists = soup.select("ol.references, div.reflist ol.references")
    if not reflists:
        return None

    refs: list[ImportedRef] = []
    for rl in reflists:
        for li in rl.find_all("li", recursive=False):
            ref = _parse_reference_li(li)
            if ref:
                refs.append(ref)

    return refs if refs else None
