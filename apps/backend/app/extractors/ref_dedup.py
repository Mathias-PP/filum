"""Deduplication multi-cles pour ImportedRef.

Regle : deux refs sont considerees identiques ssi
    - meme DOI (les deux presents ET egaux), OU
    - meme URL normalisee (les deux presentes ET egales), OU
    - meme titre norme ET meme premier auteur norme ET
      pas d'annee-conflit (les deux presentes et differentes = distinct)

L'annee est un facteur de DISTINCTION, jamais de MATCHING : absente sur
un cote = pas un blocage ; presente et differente = signal fort de refs
distinctes (republication, papiers homonymes).

Elimine les faux positifs de la dedup 2-passes precedente qui collapsait
tous les titres "Introduction" ensemble.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from app.services.import_parsers import ImportedRef, _doi_from_url


def norm_title(s: str | None) -> str:
    """Normalise un titre : NFKC + lowercase + alphanumeric only + [:80]."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^a-z0-9]", "", s)[:80]


def norm_first_author(authors: str | None) -> str:
    """Extrait et normalise le nom de famille du premier auteur.

    Gere : 'Family, G.', 'Family G.', 'G. Family', 'Family1 G., Family2 H.'
    """
    if not authors:
        return ""
    first = authors.split(",")[0].strip()
    if not first:
        return ""
    parts = first.split()
    if not parts:
        return ""
    # 'G. Family' : initiale devant, nom en dernier
    if re.match(r"^[A-Z]\.$", parts[0]) or re.match(r"^[A-Z][a-z]?\.$", parts[0]):
        candidate = parts[-1]
    else:
        candidate = parts[0]
    candidate = unicodedata.normalize("NFKC", candidate).lower()
    return re.sub(r"[^a-z]", "", candidate)


def norm_url(u: str | None) -> str:
    """Normalise une URL pour comparaison :
    - lowercase host
    - strip trailing /
    - drop scheme
    - drop les paths d'editeur post-DOI (/full, /abstract, /pdf, ...)
    """
    if not u:
        return ""
    doi = _doi_from_url(u)
    if doi:
        return f"doi:{doi}"
    try:
        parsed = urlparse(u)
    except ValueError:
        return u.lower().rstrip("/")
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").rstrip("/")
    if not host:
        return u.lower().rstrip("/")
    return f"{host}{path}".lower()


def same_ref(a: ImportedRef, b: ImportedRef) -> bool:
    """True si a et b designent la meme reference bibliographique."""
    doi_a = _doi_from_url(a.url) if a.url else None
    doi_b = _doi_from_url(b.url) if b.url else None
    if doi_a and doi_b:
        return doi_a == doi_b

    url_a = norm_url(a.url) if a.url else ""
    url_b = norm_url(b.url) if b.url else ""
    if url_a and url_b and url_a == url_b:
        return True

    title_a = norm_title(a.title)
    title_b = norm_title(b.title)
    if not title_a or not title_b:
        return False
    if title_a != title_b:
        return False

    # Titre normalise identique. Deux voies pour valider le match :
    # (a) meme premier auteur normalise (fort si les deux sont presents), ou
    # (b) titre long (>=40 chars normalises soit >~5 mots) et annees non-contradictoires
    #     — un titre long unique est un identifiant fiable meme sans auteur.
    author_a = norm_first_author(a.authors)
    author_b = norm_first_author(b.authors)
    if author_a and author_b:
        if author_a != author_b:
            return False
    elif len(title_a) < 40:
        # Titre court + auteur manquant : trop risque (homonymes du type
        # "Introduction", "Neural correlates"...). Rejet du match.
        return False

    # Titre + auteur (ou titre long) matchent. Verifier annees non-contradictoires.
    return not (a.year and b.year and a.year != b.year)


def _merge_metadata(keep: ImportedRef, drop: ImportedRef) -> ImportedRef:
    """Enrichit keep avec les champs manquants de drop."""
    if not keep.title and drop.title:
        keep.title = drop.title
    if not keep.authors and drop.authors:
        keep.authors = drop.authors
    if not keep.year and drop.year:
        keep.year = drop.year
    if not keep.url and drop.url:
        keep.url = drop.url
    if keep.category in ("page-web", "") and drop.category not in ("page-web", ""):
        keep.category = drop.category
    if not keep.raw_text and drop.raw_text:
        keep.raw_text = drop.raw_text
    if not keep.classification and drop.classification:
        keep.classification = drop.classification
    return keep


def dedupe_refs(refs: list[ImportedRef]) -> list[ImportedRef]:
    """Retourne la liste dedupee. O(n^2) mais n<500 en pratique.

    Fusionne les metadonnees quand possible : la 1ere ref rencontree est
    conservee et enrichie par les suivantes.
    """
    kept: list[ImportedRef] = []
    for ref in refs:
        matched_idx = -1
        for i, existing in enumerate(kept):
            if same_ref(existing, ref):
                matched_idx = i
                break
        if matched_idx >= 0:
            kept[matched_idx] = _merge_metadata(kept[matched_idx], ref)
        else:
            kept.append(ref)
    return kept
