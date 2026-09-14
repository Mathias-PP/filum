"""Outils web de l'agent : recherche web et lecture d'URL.

`web_search` rend des **URLs brutes** + titres + snippets, jamais une
synthèse : la vérification passe par les oracles Philum, pas par la parole du
provider. La résolution se fait à l'exécution sur l'API dédiée configurée
(`agent_web_search_provider` + `agent_web_search_api_key`, env du backend) ;
le grounding natif d'un provider et une clé BYOK de recherche sont des
extensions futures.

`fetch_url` réutilise le pipeline anti-anti-bot existant
(`app/extractors/url_extractor`) après un contrôle SSRF strict.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import httpx

from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.services.profil_modele import (
    EXTRAIT_RECHERCHE_PETIT,
    FENETRE_LECTURE_PETIT,
    PETIT_MODELE,
    RESULTATS_RECHERCHE_PETIT,
)
from app.services.texte_invisible import assainir

logger = logging.getLogger(__name__)

settings = get_settings()

_TIMEOUT = 25.0
_TEXT_MAX = 200_000


async def _rechercher(provider: str, cle: str, query: str) -> list[dict[str, str]]:
    """Les resultats du fournisseur, assainis des caracteres invisibles.

    Titres et extraits viennent d'un tiers et partent directement au modele,
    sans passer par `_texte_de_la_source` qui assainit le reste. Meme enveloppe
    ici, et pour la meme raison : quatre fournisseurs, autant de sorties, et un
    cinquieme un jour.
    """
    resultats = await _rechercher_brut(provider, cle, query)
    total = 0
    for resultat in resultats:
        for champ, valeur in resultat.items():
            resultat[champ], retires = assainir(valeur)
            total += retires
    if total:
        logger.info("recherche web : %d caracteres invisibles retires des resultats", total)
    return resultats


async def _rechercher_brut(provider: str, cle: str, query: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        if provider == "tavily":
            # La cle passe par l'en-tete, comme chez les trois autres. Tavily a
            # longtemps accepte un champ `api_key` dans le corps ; sa
            # documentation ne connait plus que `Authorization`.
            r = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {cle}"},
                json={"query": query, "max_results": 8, "search_depth": "basic"},
            )
            r.raise_for_status()
            return [
                {
                    "url": x.get("url", ""),
                    "title": x.get("title", ""),
                    "snippet": x.get("content", ""),
                }
                for x in r.json().get("results", [])
            ]
        if provider == "serper":
            r = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": cle},
                json={"q": query, "num": 8},
            )
            r.raise_for_status()
            return [
                {
                    "url": x.get("link", ""),
                    "title": x.get("title", ""),
                    "snippet": x.get("snippet", ""),
                }
                for x in r.json().get("organic", [])
            ]
        if provider == "brave":
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 8},
                headers={"X-Subscription-Token": cle, "Accept": "application/json"},
            )
            r.raise_for_status()
            return [
                {
                    "url": x.get("url", ""),
                    "title": x.get("title", ""),
                    "snippet": x.get("description", ""),
                }
                for x in r.json().get("web", {}).get("results", [])
            ]
        if provider == "exa":
            r = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": cle},
                json={"query": query, "numResults": 8},
            )
            r.raise_for_status()
            return [
                {
                    "url": x.get("url", ""),
                    "title": x.get("title", ""),
                    "snippet": x.get("text", "")[:500],
                }
                for x in r.json().get("results", [])
            ]
    raise ValueError(f"Provider de recherche web inconnu : {provider!r}.")


def fournisseurs_web() -> list[tuple[str, str]]:
    """Les moteurs configures, en paires (fournisseur, cle).

    `agent_web_search_provider` et `agent_web_search_api_key` acceptent des listes
    separees par des virgules, dans le meme ordre (« tavily,brave » et
    « cle1,cle2 »). Un seul fournisseur reste la configuration par defaut.
    """
    noms = [n.strip().lower() for n in settings.agent_web_search_provider.split(",") if n.strip()]
    cles = [c.strip() for c in settings.agent_web_search_api_key.split(",")]
    return [(nom, cles[rang]) for rang, nom in enumerate(noms) if rang < len(cles) and cles[rang]]


async def rechercher_web_fusionne(query: str) -> tuple[list[dict[str, str]], list[str]]:
    """Les resultats de tous les moteurs configures, fusionnes par rangs reciproques.

    Etude du 2026-09-14 : chaque moteur a ses angles morts, et les comparatifs
    placent Tavily sous Brave, Exa ou Parallel sur les questions a plusieurs
    sauts. Plusieurs moteurs fusionnes couvrent plus ; un moteur en panne ou a
    quota n'empeche pas les autres. Rend aussi les moteurs qui ont repondu.
    """
    from app.services.content_identity import normalize_url
    from app.services.fusion_candidates import CONSTANTE_RRF

    fournisseurs = fournisseurs_web()
    reponses = await asyncio.gather(
        *(_rechercher(provider, cle, query) for provider, cle in fournisseurs),
        return_exceptions=True,
    )
    scores: dict[str, float] = {}
    fusion: dict[str, dict[str, str]] = {}
    repondu: list[str] = []
    for (provider, _cle), reponse in zip(fournisseurs, reponses, strict=True):
        if isinstance(reponse, BaseException):
            logger.info("recherche web : %s muet (%s)", provider, reponse)
            continue
        repondu.append(provider)
        for rang, resultat in enumerate(reponse, start=1):
            cle_url = normalize_url(resultat.get("url")) or resultat.get("url", "")
            if not cle_url:
                continue
            scores[cle_url] = scores.get(cle_url, 0.0) + 1.0 / (CONSTANTE_RRF + rang)
            deja = fusion.setdefault(cle_url, {**resultat, "moteurs": provider})
            if deja is not resultat and provider not in deja["moteurs"].split(","):
                deja["moteurs"] += f",{provider}"
                deja["snippet"] = deja.get("snippet") or resultat.get("snippet", "")
    ordonnes = sorted(fusion, key=lambda cle_url: scores[cle_url], reverse=True)
    return [fusion[cle_url] for cle_url in ordonnes], repondu


async def _execute_web_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "web_search attend query (str)."}
    if len(fournisseurs_web()) > 1:
        try:
            fusionnes, repondu = await rechercher_web_fusionne(query.strip())
        except Exception as exc:  # noqa: BLE001  # message lisible par le modèle
            return {"error": f"Recherche web indisponible : {exc}"}
        if not repondu:
            return {"error": "Recherche web indisponible : aucun moteur n'a répondu."}
        if PETIT_MODELE.get():
            fusionnes = [
                {**r, "snippet": (r.get("snippet") or "")[:EXTRAIT_RECHERCHE_PETIT]}
                for r in fusionnes[:RESULTATS_RECHERCHE_PETIT]
            ]
        return {"query": query, "results": fusionnes, "moteurs": repondu}
    provider = settings.agent_web_search_provider.strip().lower()
    cle = settings.agent_web_search_api_key.strip()
    if not provider or not cle:
        return {
            "error": (
                "Recherche web non configurée sur ce serveur. "
                "Dites-le au créateur et demandez-lui les adresses : c'est la "
                "seule issue. Ne comblez jamais avec des sources reconstituées "
                "de mémoire. Ce serait d'ailleurs sans effet : `add_source` "
                "joint l'adresse avant d'écrire et refuse ce qui ne mène nulle "
                "part."
            )
        }
    try:
        resultats = await _rechercher(provider, cle, query.strip())
    except Exception as exc:  # noqa: BLE001  # message lisible par le modèle
        return {"error": f"Recherche web indisponible : {exc}"}
    if PETIT_MODELE.get():
        resultats = [
            {**r, "snippet": (r.get("snippet") or "")[:EXTRAIT_RECHERCHE_PETIT]}
            for r in resultats[:RESULTATS_RECHERCHE_PETIT]
        ]
    return {"query": query, "results": resultats}


async def _pourquoi_illisible(url: str, refuse: bool) -> str:
    """Dit pourquoi le texte manque, et ce qu'il reste a tenter.

    « Page vide ou bloquée » ne distingue pas un article payant, ou aucune
    insistance ne servira, d'un article libre momentanement bloque, qu'une
    autre route peut ouvrir. Le modele bouclait sur le premier et abandonnait
    le second.
    """
    from app.extractors.open_access import OpenAccessStatus, check_open_access
    from app.extractors.url_extractor import _extract_doi

    acces = await check_open_access(_extract_doi(url))
    if acces.status is OpenAccessStatus.CLOSED:
        return (
            "Article payant : aucune version en accès libre n'existe pour ce DOI. "
            "Le texte intégral est hors de portée. Travaillez sur le résumé, ou "
            "citez cette source sans extrait verbatim. N'inventez pas de citation."
        )
    if acces.url:
        return (
            f"Page illisible chez l'éditeur, mais une version libre existe : {acces.url}. "
            "Rappelez fetch_url sur cette adresse."
        )
    return (
        "Impossible de lire cette URL : ni l'éditeur, ni un dépôt en accès libre, "
        "ni un relais de lecture, ni l'archive du web n'en rendent le texte. "
        "Insister sur la même adresse ne changera rien. Cherchez une autre "
        "adresse pour le même contenu, ou demandez le passage au créateur. "
        "N'inventez pas d'extrait de mémoire."
    )


async def _execute_fetch_url(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    url = args.get("url")
    if not isinstance(url, str) or not url.strip():
        return {"error": "fetch_url attend url (str)."}
    url = url.strip()
    try:
        # Resolution DNS bloquante : hors du thread, un DNS lent gele tous les
        # flux SSE du worker.
        await asyncio.to_thread(assert_url_is_safe, url)
    except UnsafeUrlError as exc:
        return {"error": f"URL refusée (SSRF) : {exc}"}
    if PETIT_MODELE.get():
        return await _fenetre_de_page(url, args.get("page"))
    from app.api.v1.endpoints.excerpts import _texte_de_la_source

    texte, refuse, _complet = await _texte_de_la_source(url)
    if not texte.strip():
        return {"error": await _pourquoi_illisible(url, refuse), "blocked": refuse}
    tronque = len(texte) > _TEXT_MAX
    return {"url": url, "text": texte[:_TEXT_MAX], "truncated": tronque, "blocked": refuse}


async def _fenetre_de_page(url: str, page: Any) -> dict[str, Any]:
    """Une fenetre de la page, pour un petit modele, avec de quoi lire la suite.

    Le texte vient du cache de `texte_de_page` : lire la page 2, puis poser un
    extrait par `find_passage`, ne telecharge la page qu'une fois.
    """
    from app.services import excerpt_insertion

    texte, refuse, _complet = await excerpt_insertion.texte_de_page(url)
    if not texte.strip():
        return {"error": await _pourquoi_illisible(url, refuse), "blocked": refuse}
    try:
        numero = max(1, int(page)) if page is not None else 1
    except (TypeError, ValueError):
        numero = 1
    pages = max(1, math.ceil(len(texte) / FENETRE_LECTURE_PETIT))
    numero = min(numero, pages)
    debut = (numero - 1) * FENETRE_LECTURE_PETIT
    resultat: dict[str, Any] = {
        "url": url,
        "text": texte[debut : debut + FENETRE_LECTURE_PETIT],
        "page": numero,
        "pages": pages,
        "blocked": refuse,
    }
    if numero < pages:
        resultat["suite"] = (
            f"Page {numero} sur {pages}. fetch_url avec page={numero + 1} pour lire la "
            "suite. Pour citer un passage, find_passage cherche dans toute la page."
        )
    return resultat


def web_tools() -> list[AgentTool]:
    """Outils web disponibles selon la configuration serveur.

    ``web_search`` n'est exposé que si un fournisseur est configuré : sinon
    le modèle voit l'outil, l'appelle, reçoit ``"Recherche web non configurée"``
    et gaspille un tour (voire une session complète chez les modèles à quota
    strict comme Gemini free tier). ``fetch_url`` reste toujours disponible
    (pas de dépendance externe).
    """
    outils: list[AgentTool] = []
    if settings.agent_web_search_provider.strip() and settings.agent_web_search_api_key.strip():
        outils.append(
            AgentTool(
                name="web_search",
                description=(
                    "Recherche web. Rend des URLs brutes, titres et snippets, jamais une "
                    "synthèse : vérifie ensuite ce que tu cites via fetch_url ou "
                    "find_cards_citing."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "La requête de recherche."}
                    },
                    "required": ["query"],
                },
                output="query, results: [{url, title, snippet}]",
                execute=_execute_web_search,
            )
        )
    outils.append(
        AgentTool(
            name="fetch_url",
            description=(
                "Récupère le texte d'une page web (anti-anti-bot). Utile pour lire un contenu dont on "
                "veut extraire des sources ou des extraits verbatim."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "L'URL à lire (http/https)."},
                    "page": {
                        "type": "integer",
                        "description": (
                            "Page à lire quand la réponse en annonce plusieurs (1 par défaut)."
                        ),
                    },
                },
                "required": ["url"],
            },
            output="url, text, truncated, blocked",
            execute=_execute_fetch_url,
        )
    )
    return outils
