"""Texte plein d'un article NCBI par l'API, la ou la page HTML est murée.

PubMed et PMC servent un interstitiel reCAPTCHA aux IP de datacenter : le
scraping en rapporte zéro caractère, et la relecture des extraits conclut
« illisible » sur des articles pourtant en accès libre.

NCBI publie le même contenu en JSON structuré, sans clé ni captcha, pour son
sous-ensemble Open Access. Mesure du 2026-08-16 sur PMC7723645 : 167 535
octets et 105 passages par l'API, zéro par le scraping.

L'API accepte un PMCID comme un PMID, ce qui évite toute conversion préalable.
Un article hors accès libre reçoit un corps d'erreur en texte brut, avec un
code 200 : ne pas le distinguer du texte plein ferait déclarer introuvables
tous les extraits d'un article valide.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_HOSTS = ("pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov")
_API = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{}/unicode"
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
_TIMEOUT = 15.0


def est_url_ncbi(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _HOSTS)


def identifiant_depuis_url(url: str | None) -> str | None:
    """PMCID ou PMID porté par l'URL, sinon None."""
    if not url or not est_url_ncbi(url):
        return None
    m = re.search(r"/(PMC\d+)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r"/(\d{6,9})(?:[/?#]|$)", url)
    return m.group(1) if m else None


def texte_des_passages(corps: str) -> str | None:
    """Recolle les passages d'une réponse BioC, hors bibliographie.

    Un extrait cite le corps d'un article, jamais une ligne de sa
    bibliographie : garder la section REF ferait passer pour retrouvé un
    extrait qui n'est que le titre d'un ouvrage cité.
    """
    try:
        collections = json.loads(corps)
    except ValueError:
        return None
    if not isinstance(collections, list):
        return None
    morceaux: list[str] = []
    for collection in collections:
        for document in collection.get("documents") or []:
            for passage in document.get("passages") or []:
                if (passage.get("infons") or {}).get("section_type") == "REF":
                    continue
                texte = (passage.get("text") or "").strip()
                if texte:
                    morceaux.append(texte)
    return "\n\n".join(morceaux) if morceaux else None


async def texte_plein_ncbi(url: str | None) -> str | None:
    """URL PubMed/PMC → texte plein de l'article, ou None. Ne lève jamais."""
    identifiant = identifiant_depuis_url(url)
    if not identifiant:
        return None
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(_API.format(identifiant))
        if r.status_code != 200:
            return None
        return texte_des_passages(r.text)
    except Exception as e:
        logger.debug("API BioC NCBI indisponible pour %s : %s", url, e)
        return None
