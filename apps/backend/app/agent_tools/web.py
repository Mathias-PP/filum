"""Outils web de l'agent : recherche web et lecture d'URL.

`web_search` rend des **URLs brutes** + titres + snippets — jamais une
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
from typing import Any

import httpx

from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.core.url_safety import UnsafeUrlError, assert_url_is_safe

settings = get_settings()

_TIMEOUT = 25.0
_TEXT_MAX = 200_000


async def _rechercher(provider: str, cle: str, query: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        if provider == "tavily":
            r = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": cle, "query": query, "max_results": 8, "search_depth": "basic"},
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


async def _execute_web_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "web_search attend query (str)."}
    provider = settings.agent_web_search_provider.strip().lower()
    cle = settings.agent_web_search_api_key.strip()
    if not provider or not cle:
        return {"error": "Recherche web non configurée sur ce serveur."}
    try:
        resultats = await _rechercher(provider, cle, query.strip())
    except Exception as exc:  # noqa: BLE001 — message lisible par le modèle
        return {"error": f"Recherche web indisponible : {exc}"}
    return {"query": query, "results": resultats}


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
    from app.api.v1.endpoints.excerpts import _texte_de_la_source

    texte, refuse, _complet = await _texte_de_la_source(url)
    if not texte.strip():
        return {"error": "Impossible de lire cette URL (page vide ou bloquée).", "blocked": refuse}
    tronque = len(texte) > _TEXT_MAX
    return {"url": url, "text": texte[:_TEXT_MAX], "truncated": tronque, "blocked": refuse}


def web_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="web_search",
            description=(
                "Recherche web. Rend des URLs brutes, titres et snippets — jamais une synthèse : "
                "vérifie ensuite ce que tu cites via fetch_url ou find_cards_citing."
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
        ),
        AgentTool(
            name="fetch_url",
            description=(
                "Récupère le texte d'une page web (anti-anti-bot). Utile pour lire un contenu dont on "
                "veut extraire des sources ou des extraits verbatim."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "L'URL à lire (http/https)."}
                },
                "required": ["url"],
            },
            output="url, text, truncated, blocked",
            execute=_execute_fetch_url,
        ),
    ]
