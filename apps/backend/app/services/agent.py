"""Boucle modèle ↔ outils de l'agent BYOK.

Un tour = un appel au provider avec l'historique complet. Si le modèle
demande des outils, on exécute la séquence, on renvoie les résultats en
message ``tool``, et on relance jusqu'à ce que le modèle réponde en texte
(``done``), ou jusqu'à la borne dure (``error``).

**Sécurité, pas délégation** :
- la clé du provider est déchiffrée ici, envoyée uniquement à son endpoint
  (jamais en SSE, jamais en log) ;
- les bornes ``agent_max_tours`` / ``agent_max_turn_tokens`` coupent les
  boucles infinies et les coûts ;
- les actions sensibles sont suspendues : la boucle émet ``approval_request``
  puis *appelle* le callback ``approuver`` injecté par l'appelant (Phase 4 :
  l'utilisateur répond via l'API ; aujourd'hui l'appelant décide du refus par
  défaut) ;
- un outil n'écrit qu'avec le ``user`` authentifié du contexte : l'agent d'un
  créateur ne touche jamais les fiches d'un autre.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.philum import est_sensible
from app.agent_tools.registry import construire_registre, executer, registre_api
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.models.workspace_file import WorkspaceFile
from app.services.agent_providers import _decrypt
from app.services.llm_adapters import (
    format_chat_payload,
    parse_sse_stream_anthropic,
    protocole_pour,
    url_et_headers,
)
from app.services.llm_adapters import (
    parse_blocking_response as _adapter_parse_blocking,
)

logger = logging.getLogger(__name__)

settings = get_settings()

MAX_TOURS = settings.agent_max_tours
MAX_TURN_TOKENS = settings.agent_max_turn_tokens
_TIMEOUT = 60.0
#: Plafond de la taille d'un message ``tool`` renvoyé au modèle (le contexte
#: coûte des tokens, et les résultats d'outils sont bavards).
TOOL_RESULT_MAX = 120_000

_SYSTEME = (
    "Tu es Philum Agent, l'assistant d'un créateur de contenu scientifique. "
    "Tu utilises des outils pour lire et écrire des fiches, des sources, des "
    "extraits vérifiés, et faire des recherches web.\n\n"
    "RÈGLES ABSOLUES :\n"
    "1. Agis, ne planifie pas. N'annonce une action qu'après l'avoir exécutée. "
    "« J'ai créé... » seulement si l'outil a répondu sans erreur.\n"
    "2. Ne fabrique jamais une source, un auteur, une date ou une URL de mémoire. "
    "Si tu ne peux pas vérifier via un outil, dis-le et arrête-toi.\n"
    "3. Les extraits sont des verbatim exacts dans la langue de la source. "
    "La traduction va dans le champ `context`, jamais dans `text`.\n"
    "4. En cas d'erreur sur une valeur de champ, corrige avant de supprimer. "
    "Préfère `update_source` à `delete_source` + `add_source`.\n"
    "5. Si un outil renvoie une erreur, lis le message et corrige la valeur. "
    "Ne répète pas le même appel avec les mêmes arguments.\n"
    "6. Si la recherche web est indisponible, dis-le à l'utilisateur et arrête-toi. "
    "Ne substitue rien de ta mémoire d'entraînement.\n\n"
    "Réponds en français, en phrases courtes et factuelles."
)

#: Taille max du contexte workspace injecté dans le prompt système.
_PRIMING_MAX = 40_000

#: Taille de fenêtre de contexte par sous-chaîne de nom de modèle.
_FENETRES: dict[str, int] = {
    "gemini-2.5": 2_000_000,
    "gemini-2.0": 1_000_000,
    "gemini-1.5": 1_000_000,
    "gemini": 1_000_000,
    "claude": 200_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 128_000,
    "gpt-3.5": 16_385,
    "mistral-large": 128_000,
    "mistral": 32_000,
    "mixtral": 32_000,
}

#: Mots-clés signalant un dépassement de fenêtre de contexte.
_MOTS_DEPASSEMENT = frozenset(
    {
        "context_length_exceeded",
        "maximum context length",
        "context window",
        "exceeds the limit",
        "too many tokens",
        "prompt is too long",
        "reduce your prompt",
    }
)


def fenetre_du_modele(model: str) -> int:
    """Taille de la fenêtre de contexte d'un modèle (en tokens), repli 128 000."""
    modele_lower = model.lower()
    for prefixe, taille in _FENETRES.items():
        if prefixe in modele_lower:
            return taille
    return 128_000


def _est_depassement_contexte(erreur: str) -> bool:
    """Le message d'erreur indique-t-il un dépassement de fenêtre de contexte ?"""
    err = erreur.lower()
    return any(kw in err for kw in _MOTS_DEPASSEMENT)


def _tokens_approx(messages: list[dict[str, Any]]) -> int:
    """Estimation grossière du nombre de tokens dans une liste de messages.

    4 caractères ~ 1 token (BPE moyen occidental). Overhead par message : 8.
    """
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            total += len(content) // 4 + 8
        tcs = m.get("tool_calls")
        if isinstance(tcs, list):
            for tc in tcs:
                fn = tc.get("function", {})
                total += len(str(fn.get("arguments", ""))) // 4 + 16
    return total


def _tronquer_historique(messages: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """Tronque l'historique pour tenir dans budget tokens.

    Règles :
    - Ne sépare jamais une paire assistant(tool_calls)/tool : un tool orphelin
      est rejeté par tous les providers.
    - Insère un message de synthèse à la place du bloc retiré.
    - Si même après tout couper on dépasse, garde les 6 derniers messages.
    """
    if _tokens_approx(messages) <= budget:
        return messages

    # Construire les points de coupe valides (juste après un groupe complet)
    points: list[int] = []
    i = 0
    n = len(messages)
    while i < n:
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            j = i + 1
            while j < n and messages[j].get("role") == "tool":
                j += 1
            points.append(j)
            i = j
        else:
            points.append(i + 1)
            i += 1

    for coupe in points:
        if _tokens_approx(messages[coupe:]) <= budget:
            synthese: dict[str, Any] = {
                "role": "system",
                "content": (
                    f"[{coupe} message(s) anciens omis pour tenir "
                    "dans la fenêtre de contexte du modèle.]"
                ),
            }
            return [synthese, *messages[coupe:]]

    return messages[-6:] if len(messages) > 6 else messages


async def _priming_workspace(db: AsyncSession, creator_id: Any) -> str:
    """Charge les fichiers shared/ du workspace du créateur pour le prompt système.

    Renvoie une chaîne vide si le workspace n'est pas encore amorcé.
    """
    result = await db.execute(
        select(WorkspaceFile)
        .where(
            WorkspaceFile.creator_id == creator_id,
            WorkspaceFile.path.startswith("shared/"),
        )
        .order_by(WorkspaceFile.path)
    )
    fichiers = result.scalars().all()
    if not fichiers:
        return ""
    parties: list[str] = ["\n\n---\n## Workspace éditorial du créateur\n"]
    total = len(parties[0])
    for f in fichiers:
        bloc = f"\n### {f.path}\n{f.content}\n"
        if total + len(bloc) > _PRIMING_MAX:
            break
        parties.append(bloc)
        total += len(bloc)
    return "".join(parties)


#: Type du callback d'approbation : (id de la demande, nom de l'outil,
#: arguments) → feu vert ? Le ``request_id`` voyage jusqu'au callback parce
#: que c'est lui que le client renvoie pour répondre.
Approuver = Callable[[str, str, dict[str, Any]], Awaitable[bool]]
#: Type de l'émetteur d'événements SSE : reçoit un dict sérialisable.
Emitter = Callable[[dict[str, Any]], Awaitable[None]]


def _texte_message(message: dict[str, Any]) -> str:
    contenu = message.get("content")
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        morceaux = []
        for part in contenu:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                morceaux.append(part["text"])
        return "".join(morceaux)
    return ""


#: Retry unique sur 429 quand le provider dit combien attendre. 60 s est le
#: seuil au-dessus duquel il vaut mieux rendre la main a l'utilisateur qu'a
#: la boucle : les fenetres de contexte se ferment, l'attente devient une
#: perte perceptible.
_RETRY_MAX_ATTENTE_S = 60.0

#: Backoff court sur 502/503/504 (infrastructure instable, pas un refus).
#: Deux tentatives max, attentes [2 s, 5 s]. Au-delà, l'erreur est remontée.
_BACKOFF_5XX = (2.0, 5.0)


def _extraire_retry_delay(body: Any) -> float | None:
    """Extrait ``retryDelay`` de l'erreur Google, ou None.

    Format observe en prod le 2026-08-21 sur Gemini free tier :
    ``{"error": {"details": [{"@type": "...RetryInfo", "retryDelay": "43s"}]}}``.
    Aussi enveloppe dans une liste par Gemini (``[{"error": ...}]``).
    """
    if isinstance(body, list) and body:
        body = body[0]
    if not isinstance(body, dict):
        return None
    erreur = body.get("error")
    if not isinstance(erreur, dict):
        return None
    details = erreur.get("details")
    if not isinstance(details, list):
        return None
    for entree in details:
        if not isinstance(entree, dict):
            continue
        if "RetryInfo" in str(entree.get("@type", "")):
            delay = entree.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return float(delay[:-1])
                except ValueError:
                    return None
    return None


def _extraire_message_erreur(body: Any) -> str:
    """Le message texte d'un corps d'erreur OpenAI-compat, ou le body réduit.

    Duplique volontairement une partie de la logique de
    ``services.agent_providers._detail_provider`` : y avoir recours créerait
    un cycle d'import (agent -> providers -> agent via les tests). Cinq
    formes gérées (voir ce module pour la lecture).
    """
    if isinstance(body, list) and body:
        body = body[0]
    if isinstance(body, dict):
        erreur = body.get("error")
        if isinstance(erreur, dict):
            msg = erreur.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        if isinstance(erreur, str) and erreur.strip():
            return erreur.strip()
        for key in ("detail", "message"):
            val = body.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(body)[:400] if body else ""


def _parse_blocking_response(
    response: httpx.Response,
    provider: AgentProvider,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Parse une reponse bloquante JSON selon le protocole du provider."""
    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        msg = _extraire_message_erreur(body)
        if response.status_code == 429:
            return (
                f"Le fournisseur ({provider.provider}) refuse : quota ou limite de "
                f"débit atteinte. {msg}"
            )
        return f"Le provider a répondu HTTP {response.status_code} : {msg or body}"
    try:
        data = response.json()
    except ValueError as exc:
        return f"Réponse illisible du provider : {exc}"
    return _adapter_parse_blocking(provider.provider, data)


async def _parse_sse_stream(
    response: httpx.Response,
    on_delta: Callable[[str], Awaitable[None]] | None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Parse un flux SSE OpenAI-compat. Appelle on_delta pour chaque fragment texte.

    Gère trois cas observés en prod :
    - Format SSE standard : ``data: {...}`` par ligne
    - Format Cerebras non-SSE : JSON brut par ligne sans préfixe ``data:``
    - Fragmentation Gemini : tool_calls répartis sur plusieurs chunks,
      ``tool_call_id`` seulement dans le premier fragment ; réassemblage par index.
    - Mistral : ``finish_reason`` dans un chunk avant ``[DONE]`` ; on garde le
      dernier vu.
    """
    text_parts: list[str] = []
    tool_calls_par_index: dict[int, dict[str, Any]] = {}
    finish_reason: str | None = None
    usage: dict[str, Any] = {}
    try:
        async for ligne in response.aiter_lines():
            ligne = ligne.strip()
            if not ligne:
                continue
            if ligne.startswith("data: "):
                data_str = ligne[6:]
            elif ligne.startswith("{"):
                data_str = ligne  # Cerebras : JSON nu sans préfixe data:
            else:
                continue
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            # Usage (certains providers l'incluent dans le dernier chunk)
            if isinstance(chunk.get("usage"), dict) and chunk["usage"]:
                usage = chunk["usage"]
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0]
            if not isinstance(choice, dict):
                continue
            # Conserver le dernier finish_reason vu (Mistral le met avant [DONE])
            fr = choice.get("finish_reason")
            if fr is not None:
                finish_reason = fr
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            # Fragments texte
            content = delta.get("content")
            if isinstance(content, str) and content:
                text_parts.append(content)
                if on_delta is not None:
                    await on_delta(content)
            # Tool calls fragmentés : réassembler par index (pas par id)
            tc_list = delta.get("tool_calls")
            if isinstance(tc_list, list):
                for tc_delta in tc_list:
                    if not isinstance(tc_delta, dict):
                        continue
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_calls_par_index:
                        tool_calls_par_index[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    existing = tool_calls_par_index[idx]
                    if tc_delta.get("id"):
                        existing["id"] = tc_delta["id"]
                    if tc_delta.get("type"):
                        existing["type"] = tc_delta["type"]
                    fn_delta = tc_delta.get("function") or {}
                    if fn_delta.get("name"):
                        existing["function"]["name"] += fn_delta["name"]
                    if fn_delta.get("arguments"):
                        existing["function"]["arguments"] += fn_delta["arguments"]
    except httpx.StreamError as exc:
        return f"Erreur réseau vers le provider : {exc}"

    text = "".join(text_parts)
    tool_calls = [tool_calls_par_index[i] for i in sorted(tool_calls_par_index)]
    message: dict[str, Any] = {"role": "assistant", "content": text if text else None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message, finish_reason, usage


async def _emettre_en_un_bloc(
    resultat: tuple[dict[str, Any], str | None, dict[str, Any]] | str,
    on_delta: Callable[[str], Awaitable[None]] | None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Sur une réponse reçue d'un bloc, pousse son texte complet via ``on_delta``.

    Utilisé pour le repli 400 (provider sans streaming) comme pour un provider
    qui répond en JSON malgré ``stream=True`` : le client doit voir le texte
    arriver, fût-il d'une traite.
    """
    if not isinstance(resultat, str) and on_delta is not None:
        msg_bloc, _, _ = resultat
        texte_bloc = _texte_message(msg_bloc)
        if texte_bloc:
            await on_delta(texte_bloc)
    return resultat


async def _dispatcher_sse(
    response: httpx.Response,
    provider: AgentProvider,
    on_delta: Callable[[str], Awaitable[None]] | None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Dispatche le parsing SSE selon le protocole du provider."""
    if protocole_pour(provider.provider) == "anthropic":
        return await parse_sse_stream_anthropic(response, on_delta)
    return await _parse_sse_stream(response, on_delta)


async def _traiter_reponse_flux(
    r: httpx.Response,
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    provider: AgentProvider,
    on_delta: Callable[[str], Awaitable[None]] | None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Gère le statut HTTP d'une réponse de streaming et renvoie le résultat.

    Centralise 429 (avec retry retryDelay), 400 (repli bloquant), 200 (stream ou
    bloc selon Content-Type), et tout autre statut (erreur). Appelé depuis
    ``_appel_provider`` pour la tentative initiale ET pour chaque retry 5xx.
    """
    if r.status_code == 429:
        await r.aread()
        try:
            body_429 = r.json()
        except ValueError:
            body_429 = None
        attente = _extraire_retry_delay(body_429)
        if attente is not None and attente <= _RETRY_MAX_ATTENTE_S:
            logger.info(
                "429 sur %s, attente %.1fs puis retry (retryDelay du provider)",
                provider.model,
                attente,
            )
            await asyncio.sleep(attente)
            async with client.stream("POST", url, json=payload, headers=headers) as r2:
                if r2.status_code != 200:
                    await r2.aread()
                    try:
                        body2 = r2.json()
                    except ValueError:
                        body2 = r2.text[:500]
                    msg2 = _extraire_message_erreur(body2)
                    if r2.status_code == 429:
                        return (
                            f"Le fournisseur ({provider.provider}) refuse : quota ou "
                            f"limite de débit atteinte. {msg2}"
                        )
                    return f"Le provider a répondu HTTP {r2.status_code} : {msg2 or body2}"
                if "text/event-stream" not in r2.headers.get("content-type", ""):
                    await r2.aread()
                    return await _emettre_en_un_bloc(
                        _parse_blocking_response(r2, provider), on_delta
                    )
                return await _dispatcher_sse(r2, provider, on_delta)
        msg = _extraire_message_erreur(body_429)
        return (
            f"Le fournisseur ({provider.provider}) refuse : quota ou limite de "
            f"débit atteinte. {msg}"
        )
    if r.status_code == 400:
        await r.aread()
        logger.info("stream=True refuse (400) par %s, repli bloquant", provider.model)
        payload_bloquant = {k: v for k, v in payload.items() if k != "stream"}
        r_bloquant = await client.post(url, json=payload_bloquant, headers=headers)
        return await _emettre_en_un_bloc(_parse_blocking_response(r_bloquant, provider), on_delta)
    if r.status_code != 200:
        await r.aread()
        try:
            body = r.json()
        except ValueError:
            body = r.text[:500]
        msg = _extraire_message_erreur(body)
        return f"Le provider a répondu HTTP {r.status_code} : {msg or body}"
    if "text/event-stream" not in r.headers.get("content-type", ""):
        await r.aread()
        return await _emettre_en_un_bloc(_parse_blocking_response(r, provider), on_delta)
    return await _dispatcher_sse(r, provider, on_delta)


_CHAMPS_MESSAGE_STANDARDS = ("role", "content", "tool_calls", "tool_call_id", "name")


def _nettoyer_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ne renvoie au provider que le contrat OpenAI commun.

    Gemini signe ses tool_calls d'un ``extra_content.google.thought_signature``
    ; copie verbatim dans l'historique persiste (l'ancien code bloquant
    renvoyait le message du provider tel quel), ce champ est refuse par les
    providers stricts : Mistral repond 422 ``extra_forbidden`` des le tour
    suivant. Une session ouverte avec un provider doit pouvoir continuer sur
    un autre : on reduit chaque message a role/content/tool_call_id/name et
    chaque tool_call a id/type/function{name, arguments}.
    """
    propres: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            propres.append(m)
            continue
        propre = {k: m[k] for k in _CHAMPS_MESSAGE_STANDARDS if k in m}
        tcs = m.get("tool_calls")
        if isinstance(tcs, list):
            nettoyes: list[dict[str, Any]] = []
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn_brut = tc.get("function")
                fn: dict[str, Any] = fn_brut if isinstance(fn_brut, dict) else {}
                nettoyes.append(
                    {
                        "id": tc.get("id") or "",
                        "type": tc.get("type") or "function",
                        "function": {
                            "name": fn.get("name") or "",
                            "arguments": fn.get("arguments") or "",
                        },
                    }
                )
            propre["tool_calls"] = nettoyes
        propres.append(propre)
    return propres


async def _appel_provider(
    provider: AgentProvider,
    messages: list[dict[str, Any]],
    outils_api: list[dict[str, Any]],
    transport: httpx.AsyncBaseTransport | None,
    *,
    on_delta: Callable[[str], Awaitable[None]] | None = None,
    modele: str | None = None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Un tour. Rend ``(message, finish_reason, usage)`` ou une chaîne d'erreur.

    Tente le streaming SSE (``stream=True``) avec backoff automatique :
    - 502/503/504 : backoff [2 s, 5 s], 2 tentatives max (infrastructure instable).
    - 429 avec ``retryDelay`` : attend l'indice du provider, une fois max.
    - 400 : repli sur mode bloquant (provider sans support streaming).
    ``on_delta`` est appelée pour chaque fragment texte, au fil de l'eau.
    """
    key = _decrypt(provider.api_key_enc)
    url, headers = url_et_headers(provider.provider, provider.base_url, key)
    payload = format_chat_payload(
        provider.provider,
        modele or provider.model,
        _nettoyer_messages(messages),
        outils_api,
        MAX_TURN_TOKENS,
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=transport) as client:  # noqa: SIM117
            async with client.stream("POST", url, json=payload, headers=headers) as r:
                if r.status_code in (502, 503, 504):
                    await r.aread()
                    statut_5xx = r.status_code
                    for i, attente in enumerate(_BACKOFF_5XX):
                        logger.info(
                            "HTTP %s sur tour agent (tentative %d/%d), backoff %.0fs",
                            statut_5xx,
                            i + 1,
                            len(_BACKOFF_5XX),
                            attente,
                        )
                        await asyncio.sleep(attente)
                        async with client.stream(
                            "POST", url, json=payload, headers=headers
                        ) as r_retry:
                            statut_5xx = r_retry.status_code
                            if statut_5xx not in (502, 503, 504) or i >= len(_BACKOFF_5XX) - 1:
                                return await _traiter_reponse_flux(
                                    r_retry, client, url, payload, headers, provider, on_delta
                                )
                            await r_retry.aread()
                    return f"Le provider a répondu HTTP {statut_5xx} : infrastructure instable."
                return await _traiter_reponse_flux(
                    r, client, url, payload, headers, provider, on_delta
                )
    except httpx.HTTPError as exc:
        return f"Erreur réseau vers le provider : {exc}"
    except ValueError as exc:
        return f"Réponse illisible du provider : {exc}"


def _diagnostic_vide(
    modele: str,
    finish_reason: str | None,
    usage: dict[str, Any],
) -> str:
    """Un message d'erreur actionnable quand le modele rend un contenu vide.

    Trois cas distincts, chacun mène a une réparation différente :
    - ``length`` : le modèle a épuisé sa fenêtre. Sur Gemini/o1 en mode
      raisonnement, les tokens de pensée sont comptés dans ``max_tokens``,
      donc un budget de 8192 peut être englouti sans qu'aucune sortie visible
      ne sorte. Remède : augmenter ``agent_max_turn_tokens`` ou basculer sur
      un modèle sans raisonnement caché (``gemini-3.6-flash`` plutôt que
      ``gemini-3.7-flash`` par exemple).
    - ``content_filter`` : le filtre de sécurité a bloqué. Remède : reformuler.
    - ``stop`` avec vide : le modèle a renoncé. Souvent un signe que la
      combinaison prompt + outils déroute le modèle. Remède : reformuler ou
      changer de modèle.
    """
    tokens_completion = 0
    if isinstance(usage, dict):
        tok = usage.get("completion_tokens")
        if isinstance(tok, int):
            tokens_completion = tok
    if finish_reason == "length":
        return (
            f"Le modèle {modele} a épuisé sa fenêtre de sortie "
            f"({tokens_completion} tokens) sans produire de réponse visible. "
            "Chez Gemini et les modèles à raisonnement caché, les tokens de "
            "pensée sont comptés dans le même budget. Essayer un modèle sans "
            "raisonnement (par exemple gemini-3.6-flash) ou augmenter la "
            "limite de tokens."
        )
    if finish_reason == "content_filter":
        return f"Le filtre de sécurité de {modele} a bloqué la réponse. Reformuler la demande."
    return (
        f"Le modèle {modele} a rendu une réponse vide "
        f"(finish_reason={finish_reason or 'inconnu'}). Reformuler la demande "
        "ou changer de modèle."
    )


def _message_tool(tool_call_id: str, nom: str, resultat: dict[str, Any]) -> dict[str, Any]:
    """Message ``tool`` renvoyé au modèle après exécution.

    ``tool_call_id`` doit correspondre à l'``id`` du ``tool_calls`` renvoyé par
    l'assistant au tour précédent. La spec OpenAI l'exige ; OpenAI est tolérant
    en l'absence, mais **Gemini rejette avec HTTP 400 INVALID_ARGUMENT** dès le
    tour suivant, laissant l'utilisateur devant un chat cassé sans explication.
    Vérifié en prod le 2026-08-21 sur ``gemini-3.7-flash``.
    """
    contenu = json.dumps(resultat, ensure_ascii=False)[:TOOL_RESULT_MAX]
    return {"role": "tool", "tool_call_id": tool_call_id, "name": nom, "content": contenu}


async def _executer_tour(
    db: AsyncSession,
    user: User,
    tour: int,
    messages: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    registre: dict[str, AgentTool],
    emit: Emitter,
    approuver: Approuver,
) -> None:
    ctx = ToolContext(db=db, user=user, creator_id=user.id)
    for tc in tool_calls:
        try:
            nom = tc["function"]["name"]
        except (KeyError, TypeError):
            continue
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            args = {}
        await emit(
            {
                "type": "tool_call",
                "payload": {"id": tc.get("id"), "name": nom, "arguments": args, "tour": tour},
            }
        )
        if est_sensible(nom, args):
            request_id = str(uuid4())
            await emit(
                {
                    "type": "approval_request",
                    "payload": {
                        "request_id": request_id,
                        "tool": nom,
                        "arguments": args,
                        "tour": tour,
                    },
                }
            )
            approuve = await approuver(request_id, nom, args)
            await emit(
                {
                    "type": "approval_resolved",
                    "payload": {"request_id": request_id, "tool": nom, "approved": approuve},
                }
            )
            if not approuve:
                resultat: dict[str, Any] = {
                    "error": "Action refusée : l'utilisateur n'a pas validé cette écriture."
                }
            else:
                resultat = await executer(registre, nom, args, ctx, approbation_obtenue=True)
        else:
            resultat = await executer(registre, nom, args, ctx)
        await emit(
            {
                "type": "tool_result",
                "payload": {"id": tc.get("id"), "name": nom, "result": resultat},
            }
        )
        # Fallback si le provider a envoyé un tool_call sans id (rare mais
        # possible avec des endpoints custom) : on en synthétise un pour
        # préserver la correspondance côté message tool.
        tool_call_id = tc.get("id") or f"call_{uuid4().hex[:12]}"
        messages.append(_message_tool(tool_call_id, nom, resultat))


async def boucle(
    db: AsyncSession,
    user: User,
    provider: AgentProvider,
    messages: list[dict[str, Any]],
    emit: Emitter,
    approuver: Approuver,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    registre: dict[str, AgentTool] | None = None,
    modele: str | None = None,
) -> None:
    """Exécute la boucle jusqu'à ``done`` ou à la borne dure.

    ``messages`` est muté : le prompt système est inséré en tête, puis chaque
    tour ajoute l'assistant et les résultats d'outils. L'appelant fournit
    ``approuver`` (Phase 3 : refus par défaut, Phase 4 : approbation humaine
    réelle) et ``transport`` pour les tests.
    """
    registre = registre or construire_registre()
    outils_api = registre_api(registre)
    workspace_ctx = await _priming_workspace(db, user.id)
    systeme = {"role": "system", "content": _SYSTEME + workspace_ctx}
    messages.insert(0, systeme)

    # Troncature préventive : garder 80% de la fenêtre du modèle.
    modele_effectif = modele or provider.model
    budget = int(fenetre_du_modele(modele_effectif) * 0.8)
    if _tokens_approx(messages) > budget:
        # Ne pas tronquer le message système (index 0).
        reste = _tronquer_historique(messages[1:], budget)
        messages[1:] = reste

    usage_total: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
    contexte_compacte = False
    try:
        for tour in range(1, MAX_TOURS + 1):

            async def _on_delta(content: str, _t: int = tour) -> None:
                await emit({"type": "message_delta", "payload": {"delta": content, "tour": _t}})

            reponse = await _appel_provider(
                provider, messages, outils_api, transport, on_delta=_on_delta, modele=modele
            )
            if isinstance(reponse, str):
                if not contexte_compacte and _est_depassement_contexte(reponse):
                    # Rejeu unique : tronquer à 60% et réessayer.
                    budget_reduit = int(fenetre_du_modele(modele_effectif) * 0.6)
                    reste_reduit = _tronquer_historique(messages[1:], budget_reduit)
                    messages[1:] = reste_reduit
                    contexte_compacte = True
                    await emit(
                        {
                            "type": "contexte_compacte",
                            "payload": {"budget_tokens": budget_reduit},
                        }
                    )
                    continue
                await emit({"type": "error", "payload": {"message": reponse}})
                return
            message, finish_reason, usage = reponse
            if isinstance(usage, dict):
                usage_total["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                usage_total["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                texte = _texte_message(message)
                if texte:
                    # Texte émis en temps réel via on_delta (streaming) ou en
                    # bloc dans _appel_provider (repli bloquant). Pas de re-emit ici.
                    await emit(
                        {"type": "done", "payload": {"reason": "complete", "usage": usage_total}}
                    )
                    return
                # Contenu vide sans tool_call : silence interdit. Le modele n'a
                # rien produit d'exploitable ; on remonte le finish_reason et
                # l'usage pour que l'utilisateur puisse diagnostiquer (typique
                # sur Gemini reasoning models : finish_reason=length avec les
                # 8192 tokens consommes en pensee interne sans emettre de
                # sortie visible).
                logger.warning(
                    "Reponse vide du provider %s modele=%s finish_reason=%s usage=%s",
                    provider.provider,
                    provider.model,
                    finish_reason,
                    usage,
                )
                await emit(
                    {
                        "type": "error",
                        "payload": {
                            "message": _diagnostic_vide(provider.model, finish_reason, usage)
                        },
                    }
                )
                return
            messages.append(
                {
                    "role": "assistant",
                    "content": _texte_message(message) or None,
                    "tool_calls": tool_calls,
                }
            )
            await _executer_tour(db, user, tour, messages, tool_calls, registre, emit, approuver)
        await emit(
            {
                "type": "error",
                "payload": {"message": f"Maximum de {MAX_TOURS} tours atteint, arrêt de l'agent."},
            }
        )
    except Exception as exc:  # noqa: BLE001 -- un échec de boucle doit être visible, pas silencieux
        logger.exception("Échec de la boucle de l'agent pour %s", user.id)
        await emit({"type": "error", "payload": {"message": f"Erreur interne de l'agent : {exc}"}})
