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


def _split_author_segments(authors: str) -> list[str]:
    """Decoupe une chaine multi-auteurs en segments {1er auteur, 2eme, ...}.

    Deux formats principaux :
    - 'Family1 G., Family2 H., Family3 K.'  (S2, Crossref) -> split par ','
    - 'Family1, Given1, Family2, Given2'    (BibTeX rare)  -> paires
    - 'Family1, Given1 and Family2, Given2' (BibTeX Zotero) -> split par ' and '

    On priorise ' and ' > ';' > ',' pour separer.
    """
    s = authors.strip()
    if not s:
        return []
    # ' and ' est le separateur non ambigu (BibTeX)
    if " and " in s:
        return [x.strip() for x in s.split(" and ") if x.strip()]
    if ";" in s:
        return [x.strip() for x in s.split(";") if x.strip()]
    # Format 'Family, Given, Family, Given' (BibTeX rare) : la 2eme virgule
    # n'est pas un separateur d'auteurs mais un slot given. On detecte par
    # nombre pair de segments qui ressemblent a des (Family, Given).
    # Cas commun 'Family G., Family2 H., ...' -> split par ',' donne les auteurs.
    segments = [x.strip() for x in s.split(",") if x.strip()]
    if not segments:
        return []
    # Si le format est 'Family, Given' (comma-family-first), on a des paires
    # (Family_i, Given_i) alternees. Detecter : segments impairs sont des
    # given (courts, initiales ou prenom).
    if len(segments) >= 2 and _has_comma_family_first(f"{segments[0]}, {segments[1]}"):
        # Recombine paires
        combined = []
        for i in range(0, len(segments) - 1, 2):
            combined.append(f"{segments[i]}, {segments[i + 1]}")
        # Si nb impair, dernier segment reste tel quel
        if len(segments) % 2 == 1:
            combined.append(segments[-1])
        return combined
    return segments


def _extract_family_from_author_segment(segment: str) -> str:
    """Extrait et normalise le nom de famille d'UN segment d'auteur.

    Segment = un seul auteur sous n'importe quel format ('Wolfe C. D.',
    'C. Wolfe', 'Wolfe, C. D.', 'van der Meere J.', 'Kim-Spoon J.',
    'American Psychiatric Association' corporate).
    """
    if not segment:
        return ""
    if _is_corporate(segment):
        candidate = segment
    elif _has_comma_family_first(segment):
        candidate = _pick_family_from_segment(segment)
    else:
        candidate = _pick_family_from_segment(segment.split(",", 1)[0].strip())
    candidate = unicodedata.normalize("NFKC", candidate).lower()
    return re.sub(r"[^a-z0-9]", "", candidate)


def norm_authors_list(authors: str | None, max_authors: int = 5) -> list[str]:
    """Retourne la liste des noms de famille normalises des N premiers
    auteurs. Chaine vide → liste vide. Utilise pour la dedup plus robuste
    que le seul premier auteur.
    """
    if not authors:
        return []
    stripped = authors.strip()
    if not stripped:
        return []
    segments = _split_author_segments(stripped)[:max_authors]
    families = [_extract_family_from_author_segment(seg) for seg in segments]
    return [f for f in families if f]


def norm_first_author(authors: str | None) -> str:
    """Retour-compat : premier auteur normalise, ou '' si absent."""
    families = norm_authors_list(authors, max_authors=1)
    return families[0] if families else ""


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
    """True si a et b designent la meme reference bibliographique.

    Logique OU-inclusif :
    - meme DOI  → identique (short-circuit)
    - meme URL  → identique
    - meme (titre normalise + premier auteur normalise + annees compatibles)
      → identique MEME si les DOIs different (cas d'une reimpression du meme
      papier avec un DOI different, ex: Stroop 1935 vs sa reedition APA 1992
      avec titre et auteur identiques).
    """
    doi_a = _doi_from_url(a.url) if a.url else None
    doi_b = _doi_from_url(b.url) if b.url else None
    if doi_a and doi_b and doi_a == doi_b:
        return True  # meme DOI = meme papier, gagne toujours

    url_a = norm_url(a.url) if a.url else ""
    url_b = norm_url(b.url) if b.url else ""
    if url_a and url_b and url_a == url_b:
        return True

    # Si DOIs presents et differents, on continue vers le check titre+auteur
    # (permet de merger reimpression/version alternative du meme papier).

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
    authors_a = norm_authors_list(a.authors, max_authors=2)
    authors_b = norm_authors_list(b.authors, max_authors=2)
    if authors_a and authors_b:
        # 1er auteur doit matcher (identifiant scholarly principal).
        if authors_a[0] != authors_b[0]:
            return False
        # 2eme auteur : si present des DEUX cotes, doit matcher aussi
        # (evite de merger 2 papiers 'Wolfe C.' avec co-auteurs differents).
        # Si absent d'un cote (liste tronquee type 'Wolfe et al.'), on
        # tolere le match sur le seul 1er auteur.
        if len(authors_a) >= 2 and len(authors_b) >= 2 and authors_a[1] != authors_b[1]:
            return False
    elif len(title_a) < 40:
        # Titre court + auteur manquant des deux cotes : trop risque
        # (homonymes du type "Introduction", "Neural correlates"...).
        return False

    # Titre + auteurs (ou titre long) matchent. L'annee reste un facteur de
    # DISTINCTION : deux editions/reimpressions/republications avec meme
    # titre+auteur mais annees differentes sont des refs distinctes en
    # citation (les bibliographies citent une edition specifique).
    return not (a.year and b.year and a.year != b.year)


# Longueur (en caracteres alphanumeriques normalises) au-dela de laquelle un
# titre est considere comme un identifiant unique fiable, sans confirmation
# par les auteurs. ~40 chars = 5-6 mots.
_AUTHORITATIVE_TITLE_MIN_LEN = 40


def matches_authoritative_work(candidate: ImportedRef, authoritative: ImportedRef) -> bool:
    """True si ``candidate`` designe le meme travail qu'une ref autoritative,
    en ignorant l'annee et le DOI.

    Usage EXCLUSIF : pre-filtrage des candidats S2 contre le set autoritatif
    Crossref. S2 propose parfois une ref deja presente chez Crossref sous un
    DOI different (ex: DOI de la reedition au lieu du DOI original). Cette
    fonction detecte ces doublons pour dropper le candidat S2, l'entree
    Crossref (canonique editeur) etant conservee.

    NE PAS utiliser pour dedupliquer un set (utiliser ``same_ref`` a la place :
    deux editions/republications distinctes doivent rester distinctes).

    Couche d'enrichissement = dedup PLUS STRICTE que ``same_ref`` : un titre
    long identique suffit, meme si les chaines auteurs divergent. Les sources
    d'enrichissement degradent les auteurs de facons incompatibles (prenom vs
    nom de famille, initiales, ordre inverse) ; exiger l'egalite des auteurs
    laisse passer des doublons. Le set autoritatif etant deja complet, le cout
    d'un faux positif (perte d'une ref) est bien moindre que celui d'un faux
    negatif (doublon visible pour l'utilisateur).
    """
    title_c = norm_title(candidate.title)
    title_a = norm_title(authoritative.title)
    if not title_c or title_c != title_a:
        return False
    # Titre long identique = identifiant suffisant, sans regarder les auteurs.
    if len(title_c) >= _AUTHORITATIVE_TITLE_MIN_LEN:
        return True
    # Titre court ("Introduction", "Neural correlates") : trop d'homonymes,
    # on exige la confirmation par les auteurs.
    authors_c = norm_authors_list(candidate.authors, max_authors=2)
    authors_a = norm_authors_list(authoritative.authors, max_authors=2)
    if not authors_c or not authors_a:
        return False
    if authors_c[0] != authors_a[0]:
        return False
    # 2eme auteur : contrainte uniquement si present des deux cotes.
    return not (len(authors_c) >= 2 and len(authors_a) >= 2 and authors_c[1] != authors_a[1])


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
