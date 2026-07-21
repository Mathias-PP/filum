"""Semantic Scholar Graph API — recuperation des refs citees d'un paper.

Semantic Scholar indexe > 200M papers, avec meilleure couverture Elsevier /
ScienceDirect que Crossref (contrat d'ingestion). L'API `/paper/{id}/
references` retourne la liste des refs citees avec title / authors / year /
externalIds — pas besoin de scraper la page.

C'est la voie royale pour tout DOI scholarly : quand elle marche, on saute
le fetch HTML + le LLM entierement. Sinon fallback sur le pipeline HTML
existant.

API gratuite, sans cle. Rate limit polite pool : 100 req / 5 min. Notre
usage (1 requete par URL de contenu analysee) est tres largement sous ce
seuil.

Docs : https://api.semanticscholar.org/api-docs/graph
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
_TIMEOUT = 10.0

# Champs demandes pour chaque cited paper : minimal pour tenir sous les
# limites de payload et faire un seul roundtrip.
_REF_FIELDS = "title,authors,year,externalIds,journal"


@dataclass
class SemanticScholarRef:
    """Une reference citee par un paper, telle que renvoyee par S2."""

    title: str | None = None
    authors: str | None = None  # Concat "Family1 G., Family2 G."
    year: int | None = None
    doi: str | None = None
    # Pour les refs non-DOI (papiers arXiv, etc.) : URL calculee.
    url: str | None = None


def _format_authors(raw: list[dict] | None) -> str | None:
    """Format S2 authors → 'Family1 G., Family2 G.'."""
    if not raw:
        return None
    names: list[str] = []
    for a in raw[:10]:  # cap raisonnable
        name = a.get("name")
        if not name:
            continue
        # S2 renvoie souvent 'Given Family' — on garde tel quel, pas de
        # transformation risquee sans savoir l'ordre des composants.
        names.append(name.strip())
    return ", ".join(names) if names else None


def _extract_url_from_ext_ids(ext_ids: dict | None) -> tuple[str | None, str | None]:
    """Renvoie (doi, url_computed) a partir des externalIds S2."""
    if not ext_ids:
        return None, None
    doi = ext_ids.get("DOI")
    if doi:
        return doi.lower(), f"https://doi.org/{doi.lower()}"
    # Fallback : ArXiv
    arxiv = ext_ids.get("ArXiv")
    if arxiv:
        return None, f"https://arxiv.org/abs/{arxiv}"
    # Fallback : PubMed
    pmid = ext_ids.get("PubMed")
    if pmid:
        return None, f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return None, None


def _parse_referenced_paper(item: dict) -> SemanticScholarRef | None:
    """Extrait une SemanticScholarRef depuis un item S2 references."""
    paper = item.get("citedPaper") if isinstance(item, dict) else None
    if not isinstance(paper, dict):
        return None
    doi, url = _extract_url_from_ext_ids(paper.get("externalIds"))
    if not url:
        # Pas d'URL exploitable -> on skip cote pipeline (sera compte skipped)
        return SemanticScholarRef(
            title=paper.get("title"),
            authors=_format_authors(paper.get("authors")),
            year=paper.get("year"),
            doi=doi,
            url=None,
        )
    return SemanticScholarRef(
        title=paper.get("title"),
        authors=_format_authors(paper.get("authors")),
        year=paper.get("year"),
        doi=doi,
        url=url,
    )


async def get_paper_references(doi: str, limit: int = 500) -> list[SemanticScholarRef] | None:
    """Renvoie les refs citees par le paper identifie par ``doi``.

    Retourne ``None`` si l'API echoue (paper inconnu, timeout, rate limit).
    L'appelant doit alors fallback sur son pipeline HTML.

    ``limit`` cap la reponse : la plupart des papers ont < 200 refs, on
    default a 500 pour couvrir les reviews de litterature denses.
    """
    if not doi:
        return None
    # S2 accepte les DOIs directement dans l'URL, encode pour securite.
    from urllib.parse import quote

    encoded = quote(doi, safe="")
    url = f"{_BASE_URL}/paper/DOI:{encoded}/references?fields={_REF_FIELDS}&limit={limit}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(url)
        if r.status_code == 404:
            logger.debug("S2 paper not found: %s", doi)
            return None
        if r.status_code == 429:
            logger.warning("S2 rate-limited on doi=%s", doi)
            return None
        if r.status_code != 200:
            logger.warning("S2 HTTP %s on doi=%s: %s", r.status_code, doi, r.text[:200])
            return None
        data = r.json().get("data")
        if not isinstance(data, list):
            return None
        refs: list[SemanticScholarRef] = []
        for item in data:
            parsed = _parse_referenced_paper(item)
            if parsed is not None:
                refs.append(parsed)
        return refs
    except Exception as e:
        logger.warning("S2 references lookup failed for doi=%s: %s", doi, e)
        return None
