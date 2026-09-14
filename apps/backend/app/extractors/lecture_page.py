"""Une seule lecture de page pour nommer une source, par toutes les voies.

Mesures du 2026-09-14 :

- ameli.fr repond HTTP 403 « Vérification de sécurité » a la VM, quel que soit
  l'agent annonce, et le relais recoit le meme mur. L'archive du web porte la
  page et son titre. Le lecteur de texte des extraits passait deja par le relais
  et l'archive ; le lecteur de metadonnees ne lisait que la page directe. La meme
  source etait lisible pour la citer, illisible pour la nommer.
- le dossier Inserm : l'apercu d'import nommait trois auteurs, proposes par le
  modele de langage ; l'origine `page`, qui l'exclut, n'en nommait aucun. Deux
  lecteurs, deux verites sur la meme page.

Ici une seule fonction, dont se servent l'apercu (`url_extractor.extract`) et
l'origine `page` de `metadata_from`. Les voies sont essayees dans l'ordre de la
lecture de texte : la page directe, le relais, l'archive. Ce que le modele
propose n'est retenu que s'il figure dans le texte de la page : un titre ou un
nom lu, jamais redige.
"""

from __future__ import annotations

import logging
import re

from app.extractors import url_extractor
from app.extractors.lecteur_relais import page_par_relais
from app.extractors.url_extractor import ExtractedMetadata, _metadonnees_du_html, clean_title
from app.extractors.web_archive import html_archive

logger = logging.getLogger(__name__)

_SEPARATEURS_D_AUTEURS = re.compile(r"\s*(?:[,;]|\bet\b|\band\b|&)\s*", re.IGNORECASE)


def _pour_recherche(texte: str) -> str:
    return " ".join(texte.replace("’", "'").split()).lower()


def lu_dans(valeur: str | None, texte: str | None) -> bool:
    """La valeur figure-t-elle dans le texte, aux blancs et a la casse pres ?"""
    if not valeur or not texte:
        return False
    return _pour_recherche(valeur) in _pour_recherche(texte)


def auteurs_lus(proposes: str | None, texte: str | None) -> str | None:
    """Les auteurs proposes qui figurent un par un dans le texte, ou None."""
    if not proposes or not texte:
        return None
    noms = [n.strip() for n in _SEPARATEURS_D_AUTEURS.split(proposes) if n and n.strip()]
    retenus = [n for n in noms if len(n) > 2 and lu_dans(n, texte)]
    return ", ".join(retenus) or None


async def _completer_par_le_modele(meta: ExtractedMetadata, url: str) -> None:
    # Import local : app.services tire les modeles, qui tirent les extracteurs.
    from app.services import llm

    propose = await llm.extract_metadata(meta.page_text or "", url)
    if propose is None:
        return
    if meta.title is None and lu_dans(propose.title, meta.page_text):
        meta.title = propose.title
    if meta.authors is None:
        meta.authors = auteurs_lus(propose.authors, meta.page_text)
    if (
        meta.published_at is None
        and propose.published_at
        and propose.published_at[:4] in (meta.page_text or "")
    ):
        meta.published_at = propose.published_at
    meta.description = meta.description or propose.description
    # La nature proposee n'est qu'une suggestion : `core/nature_source.py` la
    # corrige a l'enregistrement quand les faits la contredisent.
    meta.format = meta.format or (propose.format.value if propose.format else None)
    meta.category = meta.category or (propose.category.value if propose.category else None)
    meta.author_kind = meta.author_kind or (
        propose.author_kind.value if propose.author_kind else None
    )


async def metadonnees_de_la_page(url: str, *, avec_modele: bool = True) -> ExtractedMetadata | None:
    """Les metadonnees lues sur la page, par la premiere voie qui la rend. Ne leve jamais.

    Rend la lecture directe telle quelle (refus compris) quand aucune voie ne
    nomme la page : l'appelant sait alors que le site a refuse, et non qu'il
    n'y avait rien.
    """
    # Resolue a l'appel, pas a l'import : la lecture directe reste celle du
    # module `url_extractor`, et un test qui la remplace la remplace partout.
    directe = await url_extractor._html_scrape(url)
    meta = directe if directe is not None and not directe.access_blocked and directe.title else None

    if meta is None:
        relayee = await page_par_relais(url)
        if relayee is not None and relayee[0]:
            meta = ExtractedMetadata(title=clean_title(relayee[0], None, url), page_text=relayee[1])
            logger.info("Metadonnees lues par le relais url=%s", url)

    if meta is None:
        capture = await html_archive(url)
        if capture:
            archivee = _metadonnees_du_html(capture, url)
            if not archivee.access_blocked and archivee.title:
                meta = archivee
                logger.info("Metadonnees lues dans l'archive url=%s", url)

    if meta is None:
        return directe
    if avec_modele and meta.page_text:
        await _completer_par_le_modele(meta, url)
    return meta
