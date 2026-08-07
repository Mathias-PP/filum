"""Repli : les liens poses dans le corps, quand il n'y a pas de bibliographie.

Beaucoup de contenus n'ont pas de section References : un article de presse
cite ses pieces en liant les mots du texte, un essai de blog fait pareil. Le
pipeline rendait alors zero source (mesure du 2026-08-07 sur ProPublica et
Gwern), c'est-a-dire un ecran vide la ou la page cite des dizaines de pieces.

Ces liens ne sont pas une bibliographie deposee : sur l'essai mesure, la
moitie pointait vers Wikipedia pour definir un terme, et il s'y melait du
Patreon. Ce module ne cherche donc pas a trancher ce qui est une source — il
ecarte ce qui ne peut pas en etre une (navigation, renvois internes, boutons
de partage, ancres vides) et laisse l'auteur·ice arbitrer le reste a l'ecran.
C'est aussi pourquoi ce repli n'est branche que sur les pages sans section, et
que la confiance annoncee y reste « moyenne ».
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.services.import_parsers import ImportedRef, _dedupe_key

# Chemins d'action « partager cette page » : ce sont des boutons, pas des
# citations. On filtre sur le chemin et non sur le domaine, sinon on perdrait
# toute citation d'un message precis (un tweet cite est une source legitime).
_SHARE_PATH_MARKERS = (
    "/intent/tweet",
    "/intent/post",
    "/sharearticle",
    "/sharer.php",
    "/sharer/sharer.php",
    "/share.php",
    "/submit?url=",
    "/shareopenlink",
    "/share_save",
    "/dialog/feed",
    "/dialog/share",
)

# Blocs de chrome : rien de ce qui s'y trouve n'est cite par le contenu.
_CHROME_TAGS = ("nav", "header", "footer", "aside", "script", "style", "noscript", "form")

# Un lien vers le meme site n'est le plus souvent qu'un renvoi editorial
# (« lire aussi »). Mais une institution cite ses propres rapports : la fiche
# depression de l'OMS renvoie a cinq publications de l'OMS, qui sont bien ses
# sources, et l'ecran n'en montrait qu'une. On distingue par la position — un
# lien pose au milieu d'une phrase de texte courant est une citation, un lien
# isole dans un bloc court est de la navigation.
_INLINE_SURROUNDING_MIN = 80

# Au-dela, le site fait des liens internes un dispositif de navigation plutot
# que de citation : l'essai Gwern mesure en porte 238 dans ses phrases, ce qui
# ferait passer la fiche de 78 a 316 sources. On n'en garde alors aucun, plutot
# que d'en trier arbitrairement. L'OMS en a cinq, ProPublica zero : les deux
# regimes se separent nettement.
_INTERNAL_LINKS_MAX = 20


def _registrable_host(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_cited_in_a_sentence(anchor: Tag) -> bool:
    """True si le lien est pose au milieu d'un paragraphe de texte courant."""
    paragraph = anchor.find_parent("p")
    if paragraph is None:
        return False
    around = len(paragraph.get_text(" ", strip=True)) - len(anchor.get_text(" ", strip=True))
    return around >= _INLINE_SURROUNDING_MIN


def extract_body_links(html: str, source_url: str) -> list[ImportedRef]:
    """Liens poses dans le corps de la page, hors chrome et hors navigation."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.find("main") or soup.find("article") or soup.find("body")
    if not isinstance(root, Tag):
        return []

    for tag in root(_CHROME_TAGS):
        tag.decompose()

    own_host = _registrable_host(source_url)
    refs: list[ImportedRef] = []
    internal: list[ImportedRef] = []
    seen: set[str] = set()

    for anchor in root.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if href.startswith("#") or not href:
            continue  # ancre vers la page elle-meme
        absolute = urljoin(source_url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        is_internal = _registrable_host(absolute) == own_host
        if is_internal and (
            _dedupe_key(absolute) == _dedupe_key(source_url) or not _is_cited_in_a_sentence(anchor)
        ):
            continue
        href = absolute
        lowered = href.lower()
        if any(marker in lowered for marker in _SHARE_PATH_MARKERS):
            continue
        label = anchor.get_text(" ", strip=True)
        if not label:
            continue  # sans texte, la source arrive a l'ecran sans aucun contexte
        if href in seen:
            continue
        seen.add(href)
        # Le texte du lien n'est pas un titre : « at least $3 billion » ne
        # nomme pas le rapport vise. Il part dans `raw_text` (contexte de
        # citation) et le titre reste vide pour que le backfill aille chercher
        # le vrai titre du document — ce que renseigner `title` empecherait.
        ref = ImportedRef(url=href, raw_text=label if label != href else None)
        (internal if is_internal else refs).append(ref)

    if len(internal) <= _INTERNAL_LINKS_MAX:
        refs.extend(internal)
    return refs
