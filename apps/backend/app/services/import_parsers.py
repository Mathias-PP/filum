"""Parseurs de fichiers bibliographiques → brouillons de sources.

Formats supportes : BibTeX (.bib), CSL-JSON (export Zotero), Markdown
(notes Obsidian), PDF (extraction des URLs/DOI du texte), DOCX (zipfile +
XML stdlib) et HTML sauvegarde (BeautifulSoup, deja en dependance).
Fonctions pures — le PDF est fouille via zlib (streams FlateDecode),
sans dependance d'extraction lourde.

Chaque parseur retourne des ImportedRef. Une entree sans URL ni DOI mais
avec un titre est **conservee** (url=""), car un livre, un chapitre ou un
article ancien n'a souvent aucune adresse : l'ecarter revient a amputer une
bibliographie de ses references les plus anciennes. `Source.url` accepte la
chaine vide. Seule une entree sans URL *et* sans titre — donc non
identifiable — est comptee dans `skipped`.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class ImportedRef:
    url: str
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    category: str = "page-web"
    # Metadonnees bibliographiques etendues (remplies par crossref_lookup).
    journal: str | None = None
    volume: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    # Texte brut du bloc de reference d'ou cette ref vient (Frontiers/PMC :
    # "AdlemanN. E.MenonV.BlaseyC. M. (2002). A developmental fMRI study..."
    # + DOI). Utilise en fallback LLM par-bloc quand Crossref echoue.
    # Non serialise vers l'API (usage interne pipeline uniquement).
    raw_text: str | None = None
    # Classification LLM du type d'URL : 'source' | 'promo' | 'social' | 'other'.
    # None = pas encore classifie / LLM off. L'utilisateur voit un badge dans la
    # preview et coche/decoche a sa guise -- rien n'est jamais filtre auto.
    classification: str | None = None


@dataclass
class ParseResult:
    refs: list[ImportedRef] = field(default_factory=list)
    skipped: int = 0


_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>{}]+)")
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]}]+")

# Suffixes de chemin ajoutés par les éditeurs après un DOI dans leurs URLs
# (Wiley /doi/full/10.1002/xxx, T&F /doi/pdf/10.1080/yyy, Frontiers /full,
# PLOS /article, etc.). Utilisé pour normaliser le DOI extrait d'une URL.
_DOI_PATH_SUFFIXES = re.compile(r"/(?:full|abstract|pdf|epdf|epub|meta|figures|references)$", re.I)


def _doi_to_url(doi: str) -> str:
    return f"https://doi.org/{doi.rstrip('.,;')}"


def _doi_from_url(url: str) -> str | None:
    """Extract a bare DOI from any URL that embeds one.

    Handles doi.org / dx.doi.org, DOIs in publisher URL paths
    (Frontiers /articles/10.3389/…, Wiley /doi/10.1002/…, Springer
    /article/10.1007/…), and DOIs passed as query params
    (?doi=10.xxx/yyy, URL-encoded or not — common on ScienceDirect).
    Returns lowercased DOI without trailing publisher suffixes like
    ``/full`` or ``/pdf``.
    """
    from urllib.parse import unquote

    decoded = unquote(url)
    patterns = [
        r"(?:https?://)?(?:dx\.)?doi\.org/([^\s?#]+)",
        r"[?&]doi=(10\.\d{4,9}/[^\s&#]+)",
        r"/(10\.\d{4,9}/[^\s?#]+)",
    ]
    for p in patterns:
        m = re.search(p, decoded, re.IGNORECASE)
        if m:
            doi = m.group(1).strip().rstrip(".,;)/")
            doi = _DOI_PATH_SUFFIXES.sub("", doi)
            # Vieux DOIs APA/legacy avec '//' (ex 10.1037//0012-1649.35.1.205)
            # non conformes ISO 26324 mais courants. Normaliser en '/' unique
            # pour matcher la version standard.
            doi = re.sub(r"/+", "/", doi)
            return doi.lower()
    return None


_TRUNCATION_SUFFIX_RE = re.compile(r"(?:\.{2,}|…)$")


def clean_scanned_url(raw: str) -> str | None:
    """Nettoie une URL capturee dans du texte libre. None = inutilisable.

    Deux cas distincts :
    - ponctuation de phrase collee a la fin (``…voir ici.``) -> on la retire ;
    - URL visuellement tronquee par l'affichage (``/assure/sante/the...``,
      courant dans les descriptions YouTube ou les apercus de commentaires)
      -> la cible est perdue, la garder produirait un lien mort et un
      quasi-doublon de l'URL complete. On la rejette.
    """
    url = raw.strip().rstrip("'\"")
    if _TRUNCATION_SUFFIX_RE.search(url):
        return None
    url = url.rstrip(".,;:)]}")
    return url if len(url) > 12 else None


def _dedupe_key(url: str) -> str:
    """Canonical dedup key: DOI when embedded, else the normalized URL.

    Collapses e.g. ``doi.org/10.3389/fpsyg.2018.01561`` and the Frontiers
    canonical URL ``frontiersin.org/…/10.3389/fpsyg.2018.01561/full`` to
    the same ref, since they resolve to the same article.
    """
    doi = _doi_from_url(url)
    if doi:
        return f"doi:{doi}"
    return url.rstrip("/").lower()


def _dedupe(refs: list[ImportedRef]) -> list[ImportedRef]:
    seen: set[str] = set()
    out: list[ImportedRef] = []
    for ref in refs:
        # Sans URL, l'URL ne peut pas servir de cle : toutes les refs sans
        # adresse s'effondreraient sur la meme entree vide. On les distingue
        # par ce qui les identifie reellement.
        if ref.url:
            key = _dedupe_key(ref.url)
        else:
            key = f"nourl:{(ref.title or '').strip().lower()}|"
            key += f"{(ref.authors or '').strip().lower()}|{ref.year or ''}"
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


# --- BibTeX -----------------------------------------------------------------

_BIBTEX_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", re.IGNORECASE)

#: Accents LaTeX. Un .bib exporte par un gestionnaire de references ecrit
#: « M\"uller » ou « Lev\'y » : laisser passer la sequence brute afficherait
#: « Lev\'y » dans la fiche publique.
_LATEX_ACCENTS = {
    "`": "̀",
    "'": "́",
    "^": "̂",
    "~": "̃",
    '"': "̈",
    "=": "̄",
    ".": "̇",
    "u": "̆",
    "v": "̌",
    "c": "̧",
    "H": "̋",
    "k": "̨",
    "r": "̊",
}

#: Caracteres qui n'ont pas de forme « accent + lettre » a composer.
_LATEX_LITERALS = {
    r"\ss": "ß",
    r"\ae": "æ",
    r"\AE": "Æ",
    r"\oe": "œ",
    r"\OE": "Œ",
    r"\o": "ø",
    r"\O": "Ø",
    r"\aa": "å",
    r"\AA": "Å",
    r"\l": "ł",
    r"\L": "Ł",
    r"\i": "ı",
    r"\&": "&",
    r"\%": "%",
    r"\$": "$",
    r"\_": "_",
    r"\#": "#",
    "--": "–",
    "---": "—",
    "~": " ",
}

_LATEX_ACCENT_RE = re.compile(r"\\([`'^~\"=.uvcHkr])\s*\{?\\?([a-zA-Z])\}?|\\([`'^~\"=.])\{\}")
#: Toute commande restante. On la retire plutot que de l'afficher : un
#: « \textbf » dans un titre est un artefact de format, jamais du contenu.
_LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\s*")


def latex_to_unicode(value: str) -> str:
    """Rend lisible un champ BibTeX ecrit en echappements LaTeX.

    Aucune dependance : la couverture visee est celle d'une bibliographie
    (accents, ligatures, tirets), pas celle d'un document LaTeX complet. Le
    traitement degrade proprement -- une commande inconnue est retiree, jamais
    laissee telle quelle -- pour qu'aucun `\\'e` ne parvienne au lecteur.
    """

    def _accent(m: re.Match[str]) -> str:
        mark, letter = m.group(1), m.group(2)
        if mark is None:
            return ""
        base = "i" if letter == "i" and mark else letter
        return unicodedata.normalize("NFC", base + _LATEX_ACCENTS.get(mark, ""))

    out = _LATEX_ACCENT_RE.sub(_accent, value)
    # Les plus longs d'abord : « \AA » ne doit pas etre lu comme « \A » + A.
    for token in sorted(_LATEX_LITERALS, key=len, reverse=True):
        out = out.replace(token, _LATEX_LITERALS[token])
    out = _LATEX_COMMAND_RE.sub("", out)
    return re.sub(r"\s+", " ", out.replace("{", "").replace("}", "")).strip()


_CATEGORY_BY_BIBTEX_TYPE = {
    "article": "article-scientifique",
    "inproceedings": "article-scientifique",
    "incollection": "article-scientifique",
    "phdthesis": "article-scientifique",
    "mastersthesis": "article-scientifique",
    "techreport": "communique",
    "book": "livre",
    "inbook": "livre",
    "booklet": "livre",
    "unpublished": "preprint",
}


def _parse_bibtex_fields(body: str) -> dict[str, str]:
    """Parse `champ = {valeur}` / `champ = "valeur"` / `champ = 1234`."""
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        m = re.match(r"\s*,?\s*(\w+)\s*=\s*", body[i:])
        if not m:
            break
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        ch = body[i]
        if ch == "{":
            depth = 0
            start = i + 1
            while i < n:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            value = body[start:i]
            i += 1
        elif ch == '"':
            end = body.find('"', i + 1)
            if end == -1:
                break
            value = body[i + 1 : end]
            i = end + 1
        else:
            m2 = re.match(r"[^,]*", body[i:])
            value = m2.group(0) if m2 else ""
            i += len(value)
        fields[name] = latex_to_unicode(value)
    return fields


def parse_bibtex(text: str) -> ParseResult:
    result = ParseResult()
    for m in _BIBTEX_ENTRY_RE.finditer(text):
        entry_type = m.group(1).lower()
        if entry_type in ("comment", "preamble", "string"):
            continue
        # Corps de l'entree : jusqu'a l'accolade fermante equilibree.
        start = text.index("{", m.start())
        depth = 0
        end = start
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        body = text[m.end() : end]
        fields = _parse_bibtex_fields(body)
        url = fields.get("url") or (_doi_to_url(fields["doi"]) if fields.get("doi") else None)
        title = fields.get("title") or None
        if not url and not title:
            result.skipped += 1
            continue
        year: int | None = None
        if fields.get("year", "").strip()[:4].isdigit():
            year = int(fields["year"].strip()[:4])
        result.refs.append(
            ImportedRef(
                url=url or "",
                title=title,
                authors=fields.get("author", "").replace(" and ", ", ") or None,
                year=year,
                category=_CATEGORY_BY_BIBTEX_TYPE.get(entry_type, "page-web"),
            )
        )
    result.refs = _dedupe(result.refs)
    return result


# --- CSL-JSON (export Zotero) -----------------------------------------------

_CATEGORY_BY_CSL_TYPE = {
    "article-journal": "article-scientifique",
    "paper-conference": "article-scientifique",
    "thesis": "article-scientifique",
    "report": "communique",
    "article-newspaper": "article-presse",
    "article-magazine": "article-presse",
    "book": "livre",
    "chapter": "livre",
    "webpage": "page-web",
    "post-weblog": "blog",
    "broadcast": "documentaire",
    "interview": "interview",
    "song": "podcast",
    "motion_picture": "documentaire",
}


def parse_csl_json(text: str) -> ParseResult:
    result = ParseResult()
    try:
        data = json.loads(text)
    except ValueError:
        return result
    items = data if isinstance(data, list) else data.get("items", [])
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("URL") or (_doi_to_url(item["DOI"]) if item.get("DOI") else None)
        title = item.get("title") or None
        if not url and not title:
            result.skipped += 1
            continue
        authors = None
        if isinstance(item.get("author"), list):
            names = []
            for a in item["author"]:
                if not isinstance(a, dict):
                    continue
                family = a.get("family", "")
                given = a.get("given", "")
                name = f"{family} {given}".strip() or a.get("literal", "")
                if name:
                    names.append(name)
            authors = ", ".join(names) or None
        year = None
        issued = item.get("issued")
        if isinstance(issued, dict):
            parts = issued.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                try:
                    year = int(parts[0][0])
                except (TypeError, ValueError):
                    year = None
        result.refs.append(
            ImportedRef(
                url=url or "",
                title=title,
                authors=authors,
                year=year,
                category=_CATEGORY_BY_CSL_TYPE.get(str(item.get("type", "")), "page-web"),
            )
        )
    result.refs = _dedupe(result.refs)
    return result


# --- RIS (EndNote, Mendeley, Zotero) ----------------------------------------

_CATEGORY_BY_RIS_TYPE = {
    "JOUR": "article-scientifique",
    "CONF": "article-scientifique",
    "CPAPER": "article-scientifique",
    "THES": "article-scientifique",
    "RPRT": "communique",
    "NEWS": "article-presse",
    "MGZN": "article-presse",
    "BOOK": "livre",
    "CHAP": "livre",
    "EBOOK": "livre",
    "ELEC": "page-web",
    "BLOG": "blog",
    "ICOMM": "interview",
    "SOUND": "podcast",
    "MPCT": "documentaire",
    "VIDEO": "documentaire",
}

#: « TY  - JOUR ». La norme veut deux espaces, mais les exports reels en
#: mettent un ou trois : etre strict ferait rater des fichiers valides
#: partout ailleurs.
_RIS_LINE_RE = re.compile(r"^([A-Z][A-Z0-9])\s+-\s?(.*)$")


def parse_ris(text: str) -> ParseResult:
    """Lit un fichier RIS. Un enregistrement va de ``TY`` a ``ER``.

    Un champ repete (plusieurs ``AU``) s'accumule ; les autres gardent la
    premiere valeur, car un second ``TI`` est presque toujours un sous-titre
    mal exporte plutot qu'un remplacement.
    """
    result = ParseResult()
    current: dict[str, list[str]] = {}

    def flush() -> None:
        if not current:
            return
        doi = (current.get("DO") or [""])[0].strip()
        url = (current.get("UR") or [""])[0].strip()
        if not url and doi:
            url = _doi_to_url(doi)
        title = next(
            (v[0].strip() for k in ("TI", "T1", "BT") if (v := current.get(k)) and v[0].strip()),
            None,
        )
        if not url and not title:
            result.skipped += 1
            return
        year: int | None = None
        for tag in ("PY", "Y1", "DA"):
            raw = (current.get(tag) or [""])[0].strip()[:4]
            if raw.isdigit():
                year = int(raw)
                break
        authors = ", ".join(
            a.strip() for a in current.get("AU", []) + current.get("A1", []) if a.strip()
        )
        ris_type = (current.get("TY") or [""])[0].strip().upper()
        result.refs.append(
            ImportedRef(
                url=url,
                title=title,
                authors=authors or None,
                year=year,
                category=_CATEGORY_BY_RIS_TYPE.get(ris_type, "page-web"),
            )
        )

    for raw_line in text.splitlines():
        m = _RIS_LINE_RE.match(raw_line.strip())
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "TY":
            # Un « TY » sans « ER » precedent signale un fichier tronque ou mal
            # exporte : on ferme l'enregistrement en cours plutot que de fondre
            # deux references en une.
            flush()
            current = {"TY": [value]}
        elif tag == "ER":
            flush()
            current = {}
        elif current:
            current.setdefault(tag, []).append(value)
    # Fichier sans « ER » final : la derniere reference compte quand meme.
    flush()

    result.refs = _dedupe(result.refs)
    return result


# --- Markdown (Obsidian) ----------------------------------------------------

_MD_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MD_IMAGE_RE = re.compile(r"\!\[[^\]]*\]\((https?://[^)\s]+)\)")


def parse_markdown(text: str) -> ParseResult:
    result = ParseResult()
    linked_urls: set[str] = set()
    for m in _MD_LINK_RE.finditer(text):
        title, url = m.group(1).strip(), m.group(2)
        linked_urls.add(url)
        result.refs.append(ImportedRef(url=url, title=title or None))
    # Les images ne sont pas des sources : leurs URLs sont exclues du scan nu.
    for m in _MD_IMAGE_RE.finditer(text):
        linked_urls.add(m.group(1))
    # URLs nues (hors liens deja captures)
    for m in _URL_RE.finditer(text):
        url = clean_scanned_url(m.group(0))
        if url and url not in linked_urls:
            result.refs.append(ImportedRef(url=url))
    # DOIs nus sans URL
    for m in _DOI_RE.finditer(text):
        candidate = _doi_to_url(m.group(1))
        result.refs.append(ImportedRef(candidate, category="article-scientifique"))
    result.refs = _dedupe(result.refs)
    return result


# --- Citations en texte libre (Nature/Science/APA copie-colle) --------------

# « (2009). » ou « (2009). » en fin de citation. Les intervalles retenus
# couvrent la periode ou une bibliographie moderne a ete constituee : trop
# large (1000-2099) ferait matcher des numeros de page ou des adresses.
_YEAR_PAREN_RE = re.compile(r"\((18\d{2}|19\d{2}|20\d{2})\)")

# « . Journal Vol, Pages » : la partie apres le titre. Le nom du journal peut
# contenir des abreviations avec points (« Nature Rev. Neurosci. »), c'est
# pourquoi on ne se contente pas de « [^.]+? » : chaque mot peut se terminer
# par un point. La regex s'ancre sur le motif final « Vol, Pages » (chiffres
# suivis d'une virgule et de chiffres, avec eventuellement une lettre suffixe
# comme « e123 » ou un tiret « 41-50 »).
_JOURNAL_TAIL_RE = re.compile(
    r"\.\s+"                                # separateur titre/journal
    r"[A-Z][A-Za-z]*\.?"                    # premier mot du journal
    r"(?:\s+(?:[A-Z][A-Za-z]*\.?|of|and|for|the|in|de|et))*"  # mots suivants, avec liaisons
    r"\s+\d+[a-z]?"                         # volume (« 12 », « 12a »)
    r"[,:]\s*[eE]?\d+"                      # premiere page (« 41 », « e123 »)
    r"(?:\s*[–\-]\s*\d+)?"                  # -page finale (optionnelle)
    r"\s*$"                                 # fin de chaine
)

# Entetes de section a retirer si elles precedent le premier auteur (souvent
# collees par le copier-coller depuis la page « References » d'un journal).
_LEADING_HEADER_RE = re.compile(
    r"^(?:References|Bibliography|Bibliographie|Références|Notes)\s+",
    re.IGNORECASE,
)

# Prefixe « auteurs » : nom de famille + initiales, joints par « , » ou « & »,
# terminant eventuellement par « et al. ». Reconnait « Eichenbaum, H. »,
# « Simoncelli, E. P. & Olshausen, B. A. », « Silva, A. J. et al. »,
# « Maren, S. & Quirk, G. J. », mais aussi le cas court « Marr, D. » sans
# suite. Le point final apres l'initiale est optionnel car certains styles
# l'omettent.
_AUTHORS_PREFIX_RE = re.compile(
    r"^"
    r"[A-Z][A-Za-zÀ-ÿ'\-]+"                                # nom de famille
    r"(?:,\s*[A-Z]\.(?:\s*[A-Z]\.)*)?"                     # , X. Y. (initiales pointees)
    r"(?:\s*(?:,|&)\s*"                                    # , ou & entre auteurs
    r"[A-Z][A-Za-zÀ-ÿ'\-]+"
    r"(?:,\s*[A-Z]\.(?:\s*[A-Z]\.)*)?)*"
    r"(?:\s+et\s+al\.)?"                                   # ... et al.
    r"\s+"                                                 # espace vers titre
)

# Copier-coller Nature/Science : chaque reference est suivie d'un bloc de
# tokens d'outils bibliographiques (« CAS », « PubMed », « Google Scholar »)
# separes par des lignes vides. Ces paragraphes-jetons sont du bruit.
_REFERENCE_TOOL_TOKENS = {
    "CAS", "PubMed", "PubMed Central", "Google Scholar", "ADS",
    "MathSciNet", "ISI", "Article", "Chapter", "Book",
}


def _split_authors_and_title(before_year: str) -> tuple[str | None, str | None]:
    """« Silva, A. J. et al. Titre. Journal 12, 3–4 » → (auteurs, titre).

    Heuristique en cascade : le journal (Nature Rev. Neurosci. 1, 41-50) sert
    d'ancre en fin de chaine pour retirer la partie citation ; « et al. » est
    le marqueur de fin d'auteurs le plus fiable ; a defaut, on decoupe sur
    « . » et on prend la premiere phrase qui ne ressemble pas a une suite
    d'initiales.
    """
    # Un copier-coller depuis la page d'un journal peut coller « References »
    # devant le premier auteur : cet entete parasite doit disparaitre.
    working = _LEADING_HEADER_RE.sub("", before_year, count=1)
    m = _JOURNAL_TAIL_RE.search(working)
    head = working[: m.start()].strip() if m else working.strip()
    head = head.rstrip(".").strip()
    if not head:
        return None, None

    # Approche principale : reconnaitre le prefixe auteur explicitement
    # (nom de famille + initiales, joints par « , » ou « & »). C'est plus
    #robuste que de splitter sur « . » : un titre peut commencer par « A »
    #ou « An » qu'on ne peut pas distinguer d'une initiale.
    m2 = _AUTHORS_PREFIX_RE.match(head)
    if m2:
        authors = head[: m2.end()].strip().rstrip(".").strip()
        title = head[m2.end():].strip().rstrip(".").strip()
        if title:
            return (authors or None), title

    # Fallback : pas d'auteur reconnu, tout est titre.
    return None, head


def parse_freetext_citations(text: str) -> ParseResult:
    """Extrait des references style Nature/Science : « Auteurs. Titre. Journal Vol, Pages (Annee). ».

    Utilise en secours quand un copier-coller ne contient aucune URL ni DOI :
    le HTML de Nature, par exemple, retire les liens vers les references et
    laisse la citation textuelle nue, plus des jetons « CAS / PubMed / Google
    Scholar » que ce parseur reconnait comme du bruit.
    """
    result = ParseResult()
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        one_line = " ".join(line.strip() for line in block.splitlines() if line.strip()).strip()
        if not one_line:
            continue
        if one_line in _REFERENCE_TOOL_TOKENS:
            continue
        ym = _YEAR_PAREN_RE.search(one_line)
        if not ym:
            continue
        year = int(ym.group(1))
        before = one_line[: ym.start()].rstrip()
        if before.endswith("."):
            before = before[:-1].rstrip()
        authors, title = _split_authors_and_title(before)
        if not title or len(title) < 6:
            continue
        result.refs.append(
            ImportedRef(
                url="",
                title=title,
                authors=authors,
                year=year,
                category="article-scientifique",
                raw_text=one_line,
            )
        )
    result.refs = _dedupe(result.refs)
    return result


# --- PDF --------------------------------------------------------------------


def _pdf_text_chunks(data: bytes) -> list[str]:
    """Zones lisibles d'un PDF : octets bruts + streams FlateDecode degonfles."""
    chunks = [data.decode("latin-1", errors="ignore")]
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end].rstrip(b"\r\n")
        try:
            chunks.append(zlib.decompress(raw).decode("latin-1", errors="ignore"))
        except zlib.error:
            continue
    return chunks


def parse_pdf(data: bytes) -> ParseResult:
    result = ParseResult()
    for chunk in _pdf_text_chunks(data):
        for m in _URL_RE.finditer(chunk):
            # Les operateurs PDF collent parfois du bruit apres l'URL ; on
            # coupe au premier caractere improbable dans une URL.
            url = clean_scanned_url(re.split(r"[\\(]", m.group(0))[0])
            if url:
                result.refs.append(ImportedRef(url=url))
        for m in _DOI_RE.finditer(chunk):
            doi = re.split(r"[\\(]", m.group(1))[0]
            result.refs.append(ImportedRef(_doi_to_url(doi), category="article-scientifique"))
    result.refs = _dedupe(result.refs)
    return result


# --- DOCX -------------------------------------------------------------------

_DOCX_TEXT_RE = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")
_DOCX_PARA_END_RE = re.compile(r"</w:p>")
_DOCX_HYPERLINK_RE = re.compile(
    r'Type="[^"]*/hyperlink"[^>]*Target="(https?://[^"]+)"|'
    r'Target="(https?://[^"]+)"[^>]*Type="[^"]*/hyperlink"'
)


def _docx_read(data: bytes, member: str) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return zf.read(member).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, ValueError):
        return None


def parse_docx(data: bytes) -> ParseResult:
    """Word .docx = un zip : texte dans word/document.xml (runs ``<w:t>``),
    hyperliens dans word/_rels/document.xml.rels (jamais dans le texte)."""
    document = _docx_read(data, "word/document.xml")
    if document is None:
        return ParseResult()
    # Reconstitue le texte : runs concatenes, paragraphes separes par \n.
    text = _DOCX_TEXT_RE.sub(lambda m: m.group(1), _DOCX_PARA_END_RE.sub("\n", document))
    text = re.sub(r"<[^>]+>", "", text)
    result = parse_markdown(text)
    rels = _docx_read(data, "word/_rels/document.xml.rels")
    if rels:
        for m in _DOCX_HYPERLINK_RE.finditer(rels):
            url = m.group(1) or m.group(2)
            result.refs.append(ImportedRef(url=url))
    result.refs = _dedupe(result.refs)
    return result


# --- HTML (page sauvegardee) -------------------------------------------------


def parse_html(data: bytes) -> ParseResult:
    """Page web sauvegardee : liens ``<a href>`` (texte d'ancre = titre) +
    scan des DOIs/URLs nus du texte visible (scripts et styles exclus)."""
    result = ParseResult()
    soup = BeautifulSoup(data.decode("utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    linked: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href.startswith(("http://", "https://")):
            continue
        linked.add(href)
        anchor = a.get_text(" ", strip=True)
        title = anchor if anchor and anchor != href else None
        result.refs.append(ImportedRef(url=href, title=title))
    text = soup.get_text("\n")
    for m in _URL_RE.finditer(text):
        url = clean_scanned_url(m.group(0))
        if url and url not in linked:
            result.refs.append(ImportedRef(url=url))
    for m in _DOI_RE.finditer(text):
        result.refs.append(ImportedRef(_doi_to_url(m.group(1)), category="article-scientifique"))
    result.refs = _dedupe(result.refs)
    return result


# --- Detection --------------------------------------------------------------


def detect_format(filename: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".bib") or name.endswith(".bibtex"):
        return "bibtex"
    if name.endswith(".json"):
        return "csl-json"
    if name.endswith((".ris", ".nbib", ".enw")):
        return "ris"
    if name.endswith(".md") or name.endswith(".markdown"):
        return "markdown"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith((".html", ".htm")):
        return "html"
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] == b"PK\x03\x04" and _docx_read(data, "word/document.xml") is not None:
        return "docx"
    head = data[:2000].decode("utf-8", errors="ignore").lstrip()
    if head.startswith(("[", "{")):
        return "csl-json"
    if re.search(r"@\w+\s*\{", head):
        return "bibtex"
    # Un RIS commence toujours par « TY  - » ; le chercher en tete evite de
    # confondre avec des notes Markdown qui citeraient la ligne.
    if re.search(r"^TY\s+-\s", head, re.MULTILINE):
        return "ris"
    if re.search(r"<!doctype html|<html", head, re.IGNORECASE):
        return "html"
    return "markdown"


def parse_file(filename: str | None, data: bytes, forced_format: str | None = None) -> ParseResult:
    fmt = forced_format or detect_format(filename, data)
    if fmt == "pdf":
        return parse_pdf(data)
    if fmt == "docx":
        return parse_docx(data)
    if fmt == "html":
        return parse_html(data)
    text = data.decode("utf-8", errors="replace")
    if fmt == "bibtex":
        return parse_bibtex(text)
    if fmt == "csl-json":
        return parse_csl_json(text)
    if fmt == "ris":
        return parse_ris(text)
    return parse_markdown(text)
