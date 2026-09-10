"""Metadonnees bibliographiques d'une reference, via OpenAlex.

Crossref ne connait que ce que les editeurs lui deposent. OpenAlex agrege
Crossref, PubMed, arXiv, DOAJ et les depots institutionnels, et connait donc
des references que Crossref ignore, en particulier hors des grands editeurs
anglophones. Les deux se completent : c'est pourquoi l'agent choisit l'un ou
l'autre plutot que de subir un ordre fixe.

Le work OpenAlex etait deja telecharge entier par ``check_open_access``, qui
n'en lisait que le statut d'acces et jetait le reste. Ce module lit ce reste.

Meme forme que ``crossref_lookup`` : une fonction pure qui porte la regle, et
un appel reseau qui ne fait que fournir les donnees et ne leve jamais.
"""

from __future__ import annotations

import logging

import httpx

from app.extractors.url_extractor import ExtractedMetadata

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}

#: Meme plafond que le parseur Crossref : la colonne `authors` fait 500
#: caracteres, et une liste de trente noms n'aide personne a reconnaitre un
#: article.
_MAX_AUTEURS = 5


def parser_work_openalex(work: dict | None) -> ExtractedMetadata | None:
    """Reduit un work OpenAlex aux metadonnees bibliographiques.

    Fonction pure. Rend `None` quand la reponse ne porte aucun titre : sans
    titre, la reference n'est pas identifiable, et remplir les autres champs
    donnerait une source anonyme que personne ne peut verifier.
    """
    if not work:
        return None

    titre = (work.get("display_name") or work.get("title") or "").strip()
    if not titre:
        return None

    # `display_name` est pris tel quel. OpenAlex ne separe pas toujours nom et
    # prenom de facon fiable, et deviner ou couper « van der Berg » ou un nom
    # chinois produirait des auteurs faux. Un format qui differe de celui de
    # Crossref vaut mieux qu'un nom mutile.
    noms = [
        nom
        for a in (work.get("authorships") or [])[:_MAX_AUTEURS]
        if (nom := ((a.get("author") or {}).get("display_name") or "").strip())
    ]

    emplacement = work.get("primary_location") or {}
    revue = emplacement.get("source") or {}
    biblio = work.get("biblio") or {}

    premiere = (biblio.get("first_page") or "").strip()
    derniere = (biblio.get("last_page") or "").strip()
    if premiere and derniere and premiere != derniere:
        pages = f"{premiere}-{derniere}"
    else:
        pages = premiere or derniere

    doi = (work.get("doi") or "").strip().lower()
    # OpenAlex rend le DOI en URL complete ; le reste du code manipule le DOI nu.
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")

    citations = work.get("cited_by_count")

    return ExtractedMetadata(
        title=titre[:500],
        authors=", ".join(noms)[:500] or None,
        published_at=((work.get("publication_date") or "").strip() or None),
        citations_count=citations if isinstance(citations, int) else None,
        journal=(str(revue["display_name"])[:300] if revue.get("display_name") else None),
        volume=(str(biblio["volume"])[:50] if biblio.get("volume") else None),
        pages=(pages[:50] or None),
        publisher=(
            str(revue["host_organization_name"])[:300]
            if revue.get("host_organization_name")
            else None
        ),
        doi=doi or None,
    )


async def chercher_par_doi(doi: str | None) -> ExtractedMetadata | None:
    """Interroge OpenAlex pour un DOI. Ne leve jamais.

    `None` des que le doute est permis : pas de DOI, DOI inconnu, service
    injoignable. L'appelant laisse alors les champs vides plutot que de les
    remplir d'ailleurs, ce qui ferait mentir l'origine declaree.
    """
    propre = (doi or "").strip()
    if not propre:
        return None
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(f"https://api.openalex.org/works/doi:{propre}")
        if r.status_code != 200:
            return None
        return parser_work_openalex(r.json())
    except Exception as e:
        logger.debug("OpenAlex metadata lookup failed for doi=%s: %s", propre, e)
        return None
