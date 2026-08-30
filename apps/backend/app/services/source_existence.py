"""Refuse a l'insertion les sources dont l'adresse ne mene nulle part.

Le probleme mesure en production : quand la recherche web n'est pas configuree,
l'agent repond « non configuree » puis comble avec des sources reconstituees de
memoire. Un titre plausible, des auteurs plausibles, un DOI plausible, une URL
qui n'a jamais existe. Rien dans `add_source` ne touchait le reseau : la source
entrait en base et n'etait demasquee que si un extrait lui etait attache, parce
que `prelever_dans_la_source` refuse, elle, sans preuve.

Le chemin des extraits etait donc garde et celui des sources ne l'etait pas.
Ce module ferme l'ecart, avec la meme doctrine : l'invention devient impossible
plutot que deconseillee.

Ce qui est refuse est etroit, et c'est voulu. Seule une preuve *decisive* de
non-existence bloque : le domaine n'existe pas, l'editeur repond 404 ou 410, le
DOI est inconnu de Crossref. Tout le reste passe. Un mur anti-bot (403), une
limitation de debit (429), un paywall (401), une panne de l'editeur (5xx), un
timeout : ce sont des sources qui existent et qu'on ne peut pas lire, ce qui
n'a rien a voir. Le confondre reviendrait a refuser du travail legitime, et une
garde qui mord sur l'usage reel finit desactivee.

Une source sans URL ni DOI n'est pas verifiable et n'est pas refusee : un livre
imprime n'a pas d'adresse. C'est la porte de sortie assumee, et elle a un cout
visible, puisqu'une source sans adresse ne peut porter aucun extrait verifie.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from urllib.parse import quote

import httpx

from app.core.url_safety import SAFE_REDIRECT_HOOKS, UnsafeUrlError, assert_url_is_safe

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}
_TIMEOUT = 10.0
_CROSSREF = "https://api.crossref.org/works/{}"

#: Les seuls codes qui prouvent qu'il n'y a rien a cette adresse. 404 et 410
#: sont les deux reponses par lesquelles un serveur affirme l'absence ; toutes
#: les autres decrivent un acces refuse ou une panne, donc une page existante.
_CODES_ABSENCE = frozenset({404, 410})

_INVENTION_PROBABLE = (
    "Une adresse qui ne mene nulle part vient presque toujours d'une reference "
    "reconstituee de memoire. Ne la corrigez pas au juge : citez une adresse que "
    "vous avez reellement consultee, ou dites au createur que vous n'avez pas de "
    "source pour ce point."
)


class SourceInexistanteError(Exception):
    """L'adresse a ete jointe et il n'y a rien au bout. Message pour l'agent."""


async def _crossref_connait(doi: str) -> bool | None:
    """True si Crossref publie ce DOI, False s'il l'ignore, None si indecis.

    Crossref est l'annuaire ou les editeurs deposent eux-memes leurs DOI : un
    404 y vaut preuve d'absence, ce qu'aucun editeur pris isolement ne donne.
    """
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            reponse = await client.get(_CROSSREF.format(quote(doi, safe="/")))
    except Exception as e:  # noqa: BLE001 - une panne de Crossref ne bloque rien
        logger.debug("Crossref existence check failed for doi=%s: %s", doi, e)
        return None
    if reponse.status_code == 200:
        return True
    if reponse.status_code in _CODES_ABSENCE:
        return False
    return None


async def _adresse_repond(url: str) -> int | None:
    """Le code HTTP rendu par l'adresse, ou None si la question reste ouverte.

    HEAD d'abord : la question est « y a-t-il quelque chose la », pas « qu'y
    a-t-il ». Beaucoup d'editeurs ne l'implementent pas et rendent 405 ou 501,
    d'ou le repli en GET.
    """
    try:
        await asyncio.to_thread(assert_url_is_safe, url)
    except UnsafeUrlError as exc:
        raise SourceInexistanteError(
            f"L'adresse {url} n'est pas joignable : {exc}. " + _INVENTION_PROBABLE
        ) from exc
    except socket.gaierror as exc:  # pragma: no cover - remonte deja en UnsafeUrlError
        raise SourceInexistanteError(
            f"Le domaine de {url} n'existe pas. " + _INVENTION_PROBABLE
        ) from exc

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
            event_hooks=SAFE_REDIRECT_HOOKS,
        ) as client:
            reponse = await client.head(url)
            if reponse.status_code in (405, 501):
                reponse = await client.get(url)
    except Exception as e:  # noqa: BLE001 - un reseau capricieux ne refuse rien
        logger.debug("Existence check inconclusive for url=%s: %s", url, e)
        return None
    return reponse.status_code


async def verifier_que_la_source_existe(url: str | None, doi: str | None) -> None:
    """Leve `SourceInexistanteError` si l'adresse est prouvee inexistante.

    Ne leve sur rien d'autre : ni un mur, ni un paywall, ni une panne, ni un
    timeout. Voir le docstring du module pour la raison de cette etroitesse.
    """
    if doi and (connu := await _crossref_connait(doi)) is not None:
        if not connu:
            raise SourceInexistanteError(
                f"Crossref ne connait pas le DOI {doi}. C'est l'annuaire ou les "
                "editeurs deposent eux-memes leurs DOI, donc ce numero n'a jamais "
                "ete attribue. " + _INVENTION_PROBABLE
            )
        # Crossref fait foi : un editeur qui repond 404 sur un DOI qu'il a
        # lui-meme depose decrit sa propre plomberie, pas une absence.
        return

    adresse = (url or "").strip()
    if not adresse:
        return

    if (code := await _adresse_repond(adresse)) in _CODES_ABSENCE:
        raise SourceInexistanteError(
            f"L'adresse {adresse} repond {code} : il n'y a rien a cette adresse. "
            + _INVENTION_PROBABLE
        )
