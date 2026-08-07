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

from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.services.import_parsers import ImportedRef

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


def _registrable_host(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def extract_body_links(html: str, source_url: str) -> list[ImportedRef]:
    """Liens externes poses dans le corps de la page, texte d'ancre pour titre."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.find("main") or soup.find("article") or soup.find("body")
    if not isinstance(root, Tag):
        return []

    for tag in root(_CHROME_TAGS):
        tag.decompose()

    own_host = _registrable_host(source_url)
    refs: list[ImportedRef] = []
    seen: set[str] = set()

    for anchor in root.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href.startswith(("http://", "https://")):
            continue  # ancre interne ou lien relatif : renvoi vers la page elle-meme
        if _registrable_host(href) == own_host:
            continue
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
        refs.append(ImportedRef(url=href, raw_text=label if label != href else None))

    return refs
