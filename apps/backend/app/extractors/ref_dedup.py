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


_INITIAL_RE = re.compile(r"^[A-Z]\.[A-Z]?\.?$")
# Particules de noms de famille composés (surname prefixes) — francais/allemand/
# neerlandais/italien. Doivent etre attachees au nom de famille meme si elles
# apparaissent comme mot separe : "van der Meere J." → famille = "van der meere".
_PARTICLES = {
    "van",
    "von",
    "der",
    "den",
    "de",
    "del",
    "della",
    "di",
    "da",
    "dos",
    "das",
    "du",
    "la",
    "le",
    "el",
    "al",
    "ibn",
    "bin",
    "st",
}

# Noms d'entites (organisations) qui apparaissent en champ "auteur". On les
# detecte par : plusieurs mots capitalises, pas d'initiales, longueur > 25.
_CORPORATE_HINTS = (
    "Association",
    "Society",
    "Group",
    "Committee",
    "Council",
    "Organization",
    "Institute",
    "Ministry",
    "Department",
    "Federation",
    "Consortium",
    "Team",
    "Foundation",
)


def _has_comma_family_first(segment: str) -> bool:
    """Detecte le format 'Family, Given' vs multi-auteurs comma-separated.

    Vrai (Family, Given) :
    - 'Wolfe, C. D.'          → gauche = 'Wolfe' (pas d'initiale), droite commence par initiale
    - 'van der Meere, J.'     → gauche = 'van der Meere' (pas d'initiale), droite = 'J.'
    - 'Wolfe, Christy D.'     → gauche = 'Wolfe' (1 mot), droite = 'Christy D.'

    Faux (multi-auteurs) :
    - 'Wolfe C., Bell M.'     → gauche = 'Wolfe C.' (contient initiale 'C.')
    - 'Benjamin R. Williams, J. Ponesse' → gauche = 'Benjamin R. Williams' (contient 'R.')
    - 'Diamond A., Bell M.'   → gauche = 'Diamond A.' (contient initiale)
    """
    if "," not in segment:
        return False
    left, right = segment.split(",", 1)
    left_tokens = left.strip().split()
    right_tokens = right.strip().split()
    if not left_tokens or not right_tokens:
        return False
    # Gauche = pas d'initiales (sinon c'est un auteur complet, donc multi)
    if any(_INITIAL_RE.match(t) for t in left_tokens):
        return False
    # Droite = commence par une initiale OU par un prenom (mot capitalise court)
    right_first = right_tokens[0]
    return bool(_INITIAL_RE.match(right_first)) or (
        right_first[:1].isupper() and len(right_first) <= 12
    )


def _is_corporate(authors: str) -> bool:
    """Detecte si la chaine ressemble a un nom d'entite (pas de personne)."""
    if any(h in authors for h in _CORPORATE_HINTS):
        return True
    # Aucune initiale, >= 3 mots capitalises, longueur >= 20
    if any(_INITIAL_RE.match(t) for t in authors.split()):
        return False
    caps = [t for t in authors.split() if t and t[0].isupper()]
    return len(caps) >= 3 and len(authors) >= 20


def _pick_family_from_segment(segment: str) -> str:
    """Retourne le nom de famille d'un segment nettoye (sans virgule externe).

    Formats supportes :
    - 'Family, Given'      → Family                 (via _has_comma_family_first)
    - 'Family G. H.'       → Family                 (family avant initiales)
    - 'G. Family'          → Family                 (initiales avant family)
    - 'G. H. Family'       → Family                 (2 initiales devant)
    - 'Given Family'       → Family                 (Given comme mot plein devant Family)
    - 'Given Middle Family'→ Family                 (dernier token)
    - 'van der Meere J.'   → van der Meere          (avec particules)
    - 'de la Torre A.'     → de la Torre
    - 'Kim-Spoon J.'       → Kim-Spoon              (nom compose garde tel quel)
    """
    if _has_comma_family_first(segment):
        family_part = segment.split(",", 1)[0].strip()
        return family_part

    tokens = segment.split()
    if not tokens:
        return ""

    # Retire les initiales de droite (trailing) : 'Family G. H.' → ['Family']
    # ET les initiales de gauche (leading) : 'G. Family' → ['Family']
    core = list(tokens)
    while core and _INITIAL_RE.match(core[-1]):
        core.pop()
    while core and _INITIAL_RE.match(core[0]):
        core.pop(0)

    if not core:
        # Que des initiales dans le segment (« G. F. ») → on retombe sur le
        # dernier token brut, faute de mieux.
        return tokens[-1]

    # Detecter les particules : si core commence par une (ou plusieurs)
    # particules suivies d'un mot capitalise, garder toute la sequence.
    lower0 = core[0].lower()
    if lower0 in _PARTICLES:
        return " ".join(core)  # 'van der Meere', 'de la Torre'

    # Un seul mot : c'est le nom de famille.
    if len(core) == 1:
        return core[0]

    # 2+ mots sans particule detectee : format « Given Middle Family » →
    # nom de famille = dernier token.
    return core[-1]


def norm_first_author(authors: str | None) -> str:
    """Extrait et normalise le nom de famille du premier auteur.

    Gere : 'Family, Given', 'Family G.', 'G. Family', 'Given Family',
    'Given Middle Family', 'van der Meere J.', 'de la Torre', 'Kim-Spoon J.',
    'García A.', 'American Psychiatric Association' (corporate).
    """
    if not authors:
        return ""
    stripped = authors.strip()
    if not stripped:
        return ""

    # Cas corporate : renvoyer l'entiere (pas de decoupage)
    if _is_corporate(stripped):
        candidate = stripped
    else:
        # Split par 1ere virgule uniquement si ce n'est PAS le format
        # 'Family, Given' (dans quel cas on veut garder tout le segment)
        if _has_comma_family_first(stripped):
            first_segment = stripped
        else:
            first_segment = stripped.split(",", 1)[0].strip()

        candidate = _pick_family_from_segment(first_segment)

    # Normalise NFKC + lowercase + alnum uniquement (garde les tirets internes
    # une seconde: sinon 'Kim-Spoon' devient 'kimspoon' ce qui est OK pour dedup).
    candidate = unicodedata.normalize("NFKC", candidate).lower()
    return re.sub(r"[^a-z0-9]", "", candidate)


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
