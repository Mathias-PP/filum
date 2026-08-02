"""Identite du contenu designe par une URL.

Deux references designent le meme contenu quand elles portent le meme DOI ou
la meme URL une fois normalisee. C'est le seul critere agnostique disponible :
il vaut pour un article scientifique comme pour une video, un billet de blog
ou un rapport, sans connaitre le domaine.

Il sert a reconnaitre qu'une source cite un contenu qui fait deja l'objet
d'une fiche Philum, sans que personne ait eu a poser le lien a la main.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse

# Forme canonique d'un DOI. La borne droite exclut les caracteres qui ne
# peuvent pas en faire partie mais collent souvent derriere dans un texte.
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>()\[\]{},;]+", re.IGNORECASE)

# Ponctuation de fin de phrase happee par la regex quand le DOI est cite au fil
# du texte : « ... 10.1002/wps.21122. » ne doit pas produire un DOI different.
_DOI_TRAILING = ".,;:)]}>\"'"

# Segment de vue ajoute par l'editeur derriere le DOI dans l'URL d'un article
# (Frontiers /full, Wiley /pdf...). Il designe une facon de lire le contenu,
# pas un contenu different : sans ce retrait, le DOI extrait de l'URL d'une
# fiche ne correspondrait plus a celui saisi sur la source qui la cite.
_DOI_VIEW_SUFFIXES = (
    "/full",
    "/fulltext",
    "/full-text",
    "/abstract",
    "/pdf",
    "/epdf",
    "/pdfdirect",
    "/html",
    "/meta",
    "/download",
)

# Parametres qui tracent le lecteur sans changer le contenu servi.
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "source",
}


def extract_doi(value: str | None) -> str | None:
    """Le DOI porte par un champ DOI ou noye dans une URL. Minuscules.

    Les DOI sont insensibles a la casse par specification, mais les editeurs
    les publient dans des casses differentes : sans normalisation, la meme
    reference deposee par deux editeurs ne se reconnaitrait pas.
    """
    if not value:
        return None
    match = _DOI_RE.search(value)
    if not match:
        return None
    doi = match.group(0).rstrip(_DOI_TRAILING).lower()
    for suffix in _DOI_VIEW_SUFFIXES:
        if doi.endswith(suffix):
            doi = doi[: -len(suffix)]
            break
    return doi or None


def normalize_url(url: str | None) -> str | None:
    """Forme comparable d'une URL : ``host/chemin[?requete]``.

    Le schema, le ``www.``, la barre finale, le fragment et les parametres de
    tracking ne changent pas le contenu servi. La requete restante est
    conservee et triee : sur YouTube ou une recherche, c'est elle qui porte
    l'identite du contenu.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    host = host.removeprefix("www.")
    path = parsed.path.rstrip("/")
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    )
    normalized = f"{host}{path}"
    if query:
        normalized += "?" + urlencode(query)
    return normalized


def url_variants(url: str | None) -> list[str]:
    """Les ecritures litterales d'une URL normalisee, pour une egalite SQL.

    Comparer sur la forme normalisee demanderait de normaliser en base a
    chaque ligne. On enumere plutot les quelques ecritures possibles du meme
    contenu, ce qui reste un simple ``IN`` sur une colonne indexee.
    """
    normalized = normalize_url(url)
    if not normalized:
        return []
    variants: list[str] = []
    for host_form in (normalized, "www." + normalized):
        for scheme in ("https://", "http://"):
            variants.append(scheme + host_form)
            if "?" not in host_form:
                variants.append(scheme + host_form + "/")
    return variants


def escape_like(value: str) -> str:
    """Neutralise les jokers SQL d'une valeur inseree dans un ``LIKE``.

    Un DOI peut contenir ``_``, qui vaut « n'importe quel caractere » en LIKE
    et elargirait silencieusement la correspondance.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
