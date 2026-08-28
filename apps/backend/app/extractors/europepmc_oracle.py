"""Texte plein d'un article en acces libre par Europe PMC, a partir de son DOI.

``pmc_oracle`` ne se declenche que sur une URL du domaine NCBI. Or la moitie
des sources d'une fiche scientifique sont citees par leur DOI ou par l'URL de
l'editeur, et beaucoup d'editeurs opposent un Cloudflare au scraping. L'agent
concluait « page vide ou bloquee » sur des articles integralement libres.

Mesure du 2026-08-28 sur ``10.1186/s10020-025-01205-6`` (Molecular Medicine,
CC-BY, bloque chez l'editeur) : 304 059 octets de texte integral rendus par
Europe PMC, sans cle ni captcha.

Europe PMC est un miroir de PubMed Central etendu aux depots europeens. Il ne
sert le texte integral que du sous-ensemble libre : un article ferme n'y a
qu'un resume, et ``fullTextXML`` repond alors 404. Ne pas distinguer les deux
ferait passer pour introuvable un extrait qui vit dans un corps de texte qu'on
n'a jamais eu.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx
from defusedxml import ElementTree

logger = logging.getLogger(__name__)

_RECHERCHE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_TEXTE = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
_TIMEOUT = 20.0

#: Sections a jeter : un extrait cite le corps d'un article, jamais une ligne
#: de sa bibliographie ni la legende d'un tableau. Les garder ferait passer
#: pour retrouve un extrait qui n'est que le titre d'un ouvrage cite.
_SECTIONS_HORS_CORPS = ("ref-list", "back", "table-wrap", "fn-group", "journal-meta")


def pmcid_du_resultat(charge: dict | None) -> str | None:
    """Le PMCID que Europe PMC associe a un DOI, s'il en publie le texte plein.

    ``fullTextIdList`` n'est present que pour le sous-ensemble libre : c'est
    lui qui fait foi, pas ``pmcid``, qu'un article ferme porte aussi.
    """
    if not charge:
        return None
    resultats = ((charge.get("resultList") or {}).get("result")) or []
    for resultat in resultats:
        identifiants = (resultat.get("fullTextIdList") or {}).get("fullTextId") or []
        for identifiant in identifiants:
            if str(identifiant).upper().startswith("PMC"):
                return str(identifiant).upper()
    return None


def texte_du_xml(xml: str) -> str | None:
    """Aplati un article JATS en texte, bibliographie et tableaux exclus."""
    try:
        racine = ElementTree.fromstring(xml)
    except Exception as e:  # pragma: no cover - defusedxml leve des types varies
        logger.debug("XML Europe PMC illisible : %s", e)
        return None
    corps = racine.find("body")
    if corps is None:
        return None
    for nom in _SECTIONS_HORS_CORPS:
        for noeud in corps.findall(f".//{nom}"):
            noeud.clear()
    morceaux = [m.strip() for m in corps.itertext() if m and m.strip()]
    texte = " ".join(morceaux).strip()
    return texte or None


async def _get(url: str) -> httpx.Response | None:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            return await client.get(url)
    except Exception as e:
        logger.debug("Europe PMC injoignable pour %s : %s", url, e)
        return None


async def texte_europepmc(doi: str | None) -> str | None:
    """DOI → texte integral publie par Europe PMC, ou None. Ne leve jamais.

    ``None`` ne veut pas dire « article ferme » : il couvre aussi un DOI
    inconnu du depot et un service injoignable. L'appelant qui veut annoncer
    un paywall doit le verifier ailleurs.
    """
    propre = (doi or "").strip()
    if not propre:
        return None
    reponse = await _get(f'{_RECHERCHE}?query=DOI:"{quote(propre)}"&resultType=core&format=json')
    if reponse is None or reponse.status_code != 200:
        return None
    try:
        pmcid = pmcid_du_resultat(reponse.json())
    except ValueError:
        return None
    if not pmcid:
        return None
    texte = await _get(_TEXTE.format(pmcid))
    if texte is None or texte.status_code != 200:
        return None
    return texte_du_xml(texte.text)
