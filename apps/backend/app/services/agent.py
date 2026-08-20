"""Boucle modèle ↔ outils de l'agent BYOK.

Un tour = un appel au provider avec l'historique complet. Si le modèle
demande des outils, on exécute la séquence, on renvoie les résultats en
message ``tool``, et on relance — jusqu'à ce que le modèle réponde en texte
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

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.philum import est_sensible
from app.agent_tools.registry import construire_registre, executer, registre_api
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.services.agent_providers import _decrypt
from app.services.llm import url_chat

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
    "extraits vérifiés, faire des recherches web et consulter le workspace de "
    "configuration. Réponds en phrases courtes et factuelles. Quand tu écris "
    "un extrait, cite le verbatim exact de la source. Tu ne fabriques jamais "
    "de citation : si tu ne peux pas vérifier, dis-le."
)

#: Type du callback d'approbation : (nom de l'outil, arguments) → feu vert ?
Approuver = Callable[[str, dict[str, Any]], Awaitable[bool]]
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


async def _appel_provider(
    provider: AgentProvider,
    messages: list[dict[str, Any]],
    outils_api: list[dict[str, Any]],
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[dict[str, Any], dict[str, Any]] | str:
    """Un tour. Rend ``(message, usage)`` ou une chaîne d'erreur lisible."""
    key = _decrypt(provider.api_key_enc)
    payload = {
        "model": provider.model,
        "messages": messages,
        "tools": outils_api,
        "max_tokens": MAX_TURN_TOKENS,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=transport) as client:
            r = await client.post(url_chat(provider.base_url), json=payload, headers=headers)
        if r.status_code != 200:
            try:
                detail = r.json()
            except ValueError:
                detail = r.text[:500]
            return f"Le provider a répondu HTTP {r.status_code} : {detail}"
        data = r.json()
    except httpx.HTTPError as exc:
        return f"Erreur réseau vers le provider : {exc}"
    except ValueError as exc:
        return f"Réponse illisible du provider : {exc}"
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        return f"Réponse du provider inattendue (pas de choices) : {exc}"
    usage = data.get("usage", {})
    return message, usage


def _message_tool(nom: str, resultat: dict[str, Any]) -> dict[str, Any]:
    contenu = json.dumps(resultat, ensure_ascii=False)[:TOOL_RESULT_MAX]
    return {"role": "tool", "name": nom, "content": contenu}


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
            approuve = await approuver(nom, args)
            await emit(
                {"type": "approval_resolved", "payload": {"tool": nom, "approved": approuve}}
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
        messages.append(_message_tool(nom, resultat))


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
) -> None:
    """Exécute la boucle jusqu'à ``done`` ou à la borne dure.

    ``messages`` est muté : le prompt système est inséré en tête, puis chaque
    tour ajoute l'assistant et les résultats d'outils. L'appelant fournit
    ``approuver`` (Phase 3 : refus par défaut, Phase 4 : approbation humaine
    réelle) et ``transport`` pour les tests.
    """
    registre = registre or construire_registre()
    outils_api = registre_api(registre)
    messages.insert(0, {"role": "system", "content": _SYSTEME})
    try:
        for tour in range(1, MAX_TOURS + 1):
            reponse = await _appel_provider(provider, messages, outils_api, transport)
            if isinstance(reponse, str):
                await emit({"type": "error", "payload": {"message": reponse}})
                return
            message, _usage = reponse
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                texte = _texte_message(message)
                if texte:
                    await emit({"type": "message_delta", "payload": {"delta": texte, "tour": tour}})
                await emit({"type": "done", "payload": {"reason": "complete"}})
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
    except Exception as exc:  # noqa: BLE001 — un échec de boucle doit être visible, pas silencieux
        logger.exception("Échec de la boucle de l'agent pour %s", user.id)
        await emit({"type": "error", "payload": {"message": f"Erreur interne de l'agent : {exc}"}})
