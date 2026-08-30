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
import email.utils
import json
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_tools.objectif import OUTILS_OBJECTIF
from app.agent_tools.philum import OUTILS_QUI_ECRIVENT, est_sensible
from app.agent_tools.registry import construire_registre, executer, filtrer, registre_api
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.models.agent_provider import AgentProvider
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.models.workspace_file import WorkspaceFile
from app.services.agent_approvals import DELAI_MAX as DELAI_APPROBATION
from app.services.agent_definitions import AgentDefinition
from app.services.agent_providers import _decrypt
from app.services.agent_sessions import (
    BUDGET_APRES_REFUS,
    BUDGET_HISTORIQUE,
    compacter,
    objectif_courant,
)
from app.services.llm_adapters import (
    format_chat_payload,
    parse_sse_stream_anthropic,
    protocole_pour,
    url_et_headers,
)
from app.services.llm_adapters import (
    parse_blocking_response as _adapter_parse_blocking,
)
from app.services.token_meter import TokenMeter

logger = logging.getLogger(__name__)

settings = get_settings()

MAX_TOURS = settings.agent_max_tours
MAX_TURN_TOKENS = settings.agent_max_turn_tokens
_TIMEOUT = 60.0
#: Plafond de la taille d'un message ``tool`` renvoyé au modèle (le contexte
#: coûte des tokens, et les résultats d'outils sont bavards).
TOOL_RESULT_MAX = 120_000
#: Mur d'horloge sur l'intégralité de la boucle (5 min). Empêche une boucle
#: de tourner indéfiniment si le modèle produit des tool calls en boucle.
BOUCLE_TIMEOUT = 300.0

#: Budget par appel d'outil.
#:
#: Sans lui, un seul `fetch_url` lent mangeait les 300 s de `BOUCLE_TIMEOUT` et
#: coupait le tour entier, y compris les appels qui n'avaient rien demandé. Le
#: dépassement rend une erreur que le modèle peut lire ; il ne tue pas le tour.
TIMEOUT_OUTIL = 60.0

#: Outils légitimement lents, à qui le budget par défaut ferait échouer des
#: pages parfaitement saines. Tous restent sous `BOUCLE_TIMEOUT` : un budget
#: qui l'atteindrait ne servirait à rien, la boucle serait coupée avant que le
#: modèle ait pu lire l'erreur.
TIMEOUTS_PAR_OUTIL: dict[str, float] = {
    "fetch_url": 120.0,
    "web_search": 90.0,
    "import_from_content_url": 180.0,
    "add_sources_batch": 180.0,
    "archive_sources": 180.0,
    "verify_excerpts": 180.0,
    "suggest_excerpts": 120.0,
    "get_url_metadata": 90.0,
}

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


def _contexte_temporel(maintenant: datetime | None = None) -> str:
    """La date du jour, à mettre en tête du prompt système.

    La règle 2 interdit de fabriquer une date de mémoire, et rien ne disait au
    modèle quel jour on est : il datait donc au petit bonheur de son cutoff
    d'entraînement. La date est calculée à l'appel et non au chargement du
    module, sinon un processus qui vit plusieurs jours sert une date périmée.
    """
    jour = (maintenant or datetime.now(UTC)).date().isoformat()
    return (
        f"Date du jour : {jour} (UTC). Toute date que tu avances doit venir de "
        "cette ligne ou d'un résultat d'outil, jamais de ta mémoire "
        "d'entraînement, qui s'arrête avant aujourd'hui.\n\n"
    )


async def _contexte_objectif(db: AsyncSession, creator_id: UUID, session_id: UUID | None) -> str:
    """L'objectif de la session, réinjecté à chaque tour.

    C'est tout l'intérêt de le stocker hors de l'historique : la compaction
    ampute le début de la conversation, donc la demande de départ. Relu ici, il
    survit à toutes les compactions du monde.

    Rend la chaîne vide quand aucun objectif n'est posé, plutôt qu'une section
    creuse : un titre suivi de rien apprend au modèle que la section ne veut
    rien dire.
    """
    if session_id is None:
        return ""
    objectif, phase = await objectif_courant(db, creator_id, session_id)
    if not objectif:
        return ""
    bloc = f"\n\n---\n## Objectif de cette conversation\n{objectif}\n"
    if phase:
        bloc += f"\nPhase en cours : {phase}\n"
    bloc += (
        "\nCet objectif vient de `definir_objectif`, pas de l'historique : il est "
        "vrai même si le début de la conversation a été compacté. S'il ne "
        "correspond plus à ce que le créateur demande, rappelle `definir_objectif`.\n"
    )
    return bloc


#: Une annonce de résultat déjà obtenu, au passé.
#:
#: La règle 1 du prompt système l'interdit déjà, et une conversation réelle de
#: production montre qu'une règle de prompt ne suffit pas : le modèle a annoncé
#: des actions qu'il n'avait jamais faites. Le motif reste étroit à dessein,
#: passé composé à la première personne ou constat d'achèvement, parce qu'un
#: faux positif coûte un tour de modèle. La négation ne matche pas : « je n'ai
#: pas créé » ne porte pas « j'ai ».
_ANNONCE_FAITE = re.compile(
    r"\b(?:j'ai|je viens de|nous avons)\b[^.!?\n]{0,60}?"
    r"\b(?:cr[ée]{2}\w*|ajout\w*|supprim\w*|modifi\w*|publi\w*|enregistr\w*"
    r"|import\w*|v[ée]rifi\w*|mis à jour)\b"
    r"|\bc'est (?:fait|cr[ée]{2}|ajout[ée]|publi[ée]|supprim[ée]|enregistr[ée])\b",
    re.IGNORECASE,
)

#: Ce qu'on dit au modèle quand son texte final annonce ce qu'il n'a pas fait.
_CONTROLE_RELANCE = (
    "Contrôle automatique : ta réponse annonce une action accomplie, mais aucun "
    "outil d'écriture n'a été appelé de tout ce tour. Soit tu exécutes "
    "maintenant l'action annoncée en appelant l'outil, soit tu réécris ta "
    "réponse en disant exactement ce qui n'a pas été fait et pourquoi. "
    "N'annonce jamais un résultat que tu n'as pas obtenu."
)

#: Taille max du contexte workspace injecté dans le prompt système.
_PRIMING_MAX = 40_000

#: Marqueurs d'un refus pour fenêtre de contexte saturée. La boucle de chat ne
#: passe pas par les cadrages de ``agent_providers`` : elle rend le message brut
#: du fournisseur, donc en anglais. Chacun de ces fragments a été relevé dans
#: une réponse réelle (OpenAI, Anthropic, Google, Mistral, llama.cpp).
_MARQUEURS_CONTEXTE_SATURE = (
    "context_length_exceeded",
    "maximum context length",
    "context window",
    "context length",
    "too many tokens",
    "prompt is too long",
    "reduce the length of the messages",
)


def _est_contexte_sature(erreur: str) -> bool:
    """L'erreur du fournisseur dit-elle que la fenêtre de contexte a débordé ?"""
    minuscule = erreur.lower()
    return any(marqueur in minuscule for marqueur in _MARQUEURS_CONTEXTE_SATURE)


async def _priming_workspace(
    db: AsyncSession, creator_id: Any, chemins: Sequence[str] | None = None
) -> str:
    """Charge des fichiers du workspace du créateur pour le prompt système.

    Sans ``chemins``, injecte tout `shared/` : c'est le comportement de
    l'assistant généraliste. Avec, n'injecte que ce que l'agent demande, ce
    qui divise le contexte par cinq à dix sur un agent d'étape.

    Un chemin absent est ignoré : supprimer un fichier de référence ne doit
    pas empêcher les agents qui le citaient de démarrer.

    Renvoie une chaîne vide si le workspace n'est pas encore amorcé.
    """
    stmt = select(WorkspaceFile).where(WorkspaceFile.creator_id == creator_id)
    if chemins is None:
        stmt = stmt.where(WorkspaceFile.path.startswith("shared/"))
    elif chemins:
        stmt = stmt.where(WorkspaceFile.path.in_(list(chemins)))
    else:
        return ""
    result = await db.execute(stmt.order_by(WorkspaceFile.path))
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


async def _titre_source(db: AsyncSession, source_id: str) -> tuple[str, int]:
    """Rend (titre, nombre d'extraits) pour une source. Fallback : identifiant tronqué."""
    try:
        uid = UUID(source_id)
    except (ValueError, TypeError, AttributeError):
        return str(source_id)[:12] or "source", 0
    source = await db.get(Source, uid)
    if source is None:
        return f"source {str(uid)[:8]}", 0
    r = await db.execute(
        select(func.count()).select_from(SourceExcerpt).where(SourceExcerpt.source_id == uid)
    )
    total = int(r.scalar_one_or_none() or 0)
    titre = source.title or source.url or f"source {str(uid)[:8]}"
    return titre, total


async def _titre_fiche(db: AsyncSession, user: User, slug: str) -> str:
    """Rend le titre d'une fiche du créateur ; fallback : le slug lui-même."""
    if not slug:
        return "fiche inconnue"
    r = await db.execute(
        select(BiblioCard).where(BiblioCard.slug == slug, BiblioCard.user_id == user.id)
    )
    card = r.scalar_one_or_none()
    return card.title if card else slug


async def _etat_avant_publication(db: AsyncSession, user: User, slug: str) -> str:
    """Décrit ce que la fiche porte réellement, au moment où on demande à publier.

    « Publier la fiche X ? » n'apprend rien : l'utilisateur voit le titre qu'il
    connaît déjà et pas ce que l'agent a effectivement construit. Une fiche sans
    source ou dont aucun extrait n'a été retrouvé dans sa page est publiable,
    mais il faut le dire avant, pas le découvrir en ligne.
    """
    r = await db.execute(
        select(BiblioCard).where(BiblioCard.slug == slug, BiblioCard.user_id == user.id)
    )
    card = r.scalar_one_or_none()
    if card is None:
        return f"Publier la fiche « {slug} » et la rendre visible publiquement ?"

    sources = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Source)
                .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        or 0
    )
    extraits, verifies = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(SourceExcerpt.verified_status == "found"),
            )
            .select_from(SourceExcerpt)
            .join(Source, SourceExcerpt.source_id == Source.id)
            .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
        )
    ).one()

    if sources == 0:
        etat = "Elle ne porte aucune source."
    else:
        etat = f"{sources} source{'s' if sources > 1 else ''}"
        if extraits == 0:
            etat += ", aucun extrait."
        elif verifies == extraits:
            etat += (
                f", {extraits} extrait{'s' if extraits > 1 else ''} "
                f"retrouvé{'s' if extraits > 1 else ''} dans leur source."
            )
        else:
            etat += (
                f", {extraits} extrait{'s' if extraits > 1 else ''} dont "
                f"{verifies} retrouvé{'s' if verifies > 1 else ''} dans leur source."
            )
    return f"Publier « {card.title} » et la rendre visible publiquement ? {etat}"


async def _resume_approbation(
    db: AsyncSession,
    user: User,
    tool_name: str,
    args: dict[str, Any],
) -> str:
    """Décrit en une phrase ce que l'utilisateur autorise, en résolvant UUIDs et slugs.

    Une approbation sur ``delete_source(source_id="uuid...")`` est un chèque en
    blanc si on n'affiche pas le titre réel de la source. Ce résumé est calculé
    ici parce que seul le serveur peut lire la base ; le front n'a que l'UUID.
    """
    try:
        if tool_name == "delete_source":
            titre, n = await _titre_source(db, str(args.get("source_id", "")))
            if n > 0:
                return f"Supprimer la source « {titre} » et ses {n} extrait{'s' if n > 1 else ''} ?"
            return f"Supprimer la source « {titre} » ?"
        if tool_name == "delete_excerpt":
            titre, _ = await _titre_source(db, str(args.get("source_id", "")))
            return f"Supprimer un extrait de la source « {titre} » ?"
        if tool_name == "delete_card":
            titre = await _titre_fiche(db, user, str(args.get("slug", "")))
            return f"Envoyer la fiche « {titre} » et toutes ses sources à la corbeille ?"
        if tool_name == "publish_card":
            return await _etat_avant_publication(db, user, str(args.get("slug", "")))
        if tool_name == "update_card" and args.get("visibility") == "public":
            titre = await _titre_fiche(db, user, str(args.get("slug", "")))
            return f"Publier la fiche « {titre} » (rendre publique) ?"
        if tool_name == "create_content_attestation":
            titre = await _titre_fiche(db, user, str(args.get("card_slug", "")))
            return f"Signer cryptographiquement le contenu de la fiche « {titre} » ?"
        if tool_name == "archive_sources":
            ids = args.get("source_ids") or []
            n = len(ids) if isinstance(ids, list) else 0
            return f"Déclencher l'archivage Wayback de {n} source{'s' if n > 1 else ''} ?"
    except Exception:  # noqa: BLE001 — un résumé raté ne doit pas bloquer l'approbation
        logger.exception("resume_approbation a échoué pour %s", tool_name)
    return f"Exécuter l'action sensible {tool_name} ?"


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

#: Faits du graphe injectes d'office dans le prompt systeme. Le rappel est
#: automatique et son cout est paye a chaque tour : il doit rester previsible.
#: Quand la borne mord, on le dit au modele plutot que de tronquer en silence,
#: pour qu'il sache que `recall_memory` peut en rendre davantage.
_GRAPHE_FAITS_MAX = 12


def _extraire_retry_after(header: str | None) -> float | None:
    """Extrait un delai (secondes) du header HTTP standard ``Retry-After``.

    Supporte les deux formes : secondes entieres (``Retry-After: 43``) et
    date HTTP (``Retry-After: Wed, 21 Oct 2026 07:28:00 GMT``). Renvoie None
    quand le header est absent ou illisible. Couvre les providers OpenAI-compat
    (OpenAI, Mistral, ...) qui n'incluent pas le ``retryDelay`` Google dans leur
    corps d'erreur.
    """
    if not header:
        return None
    valeur = header.strip()
    if valeur.isdigit():
        return float(valeur)
    try:
        date = email.utils.parsedate_to_datetime(valeur)
    except (TypeError, ValueError):
        return None
    if date is None:
        return None
    delai = (date - datetime.now(UTC)).total_seconds()
    return delai if delai > 0 else None


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
            # Tool calls fragmentés : réassembler par index (pas par id).
            # Deux protocoles observes :
            # - OpenAI/Anthropic standard : chaque delta porte `index`, le
            #   `name` vient dans le premier chunk et est absent apres,
            #   seuls `arguments` s'accumulent.
            # - Gemini via l'adapter OpenAI-compat : n'envoie PAS d'`index`
            #   et empile plusieurs `tool_calls` distincts sur le meme
            #   position ordinale. Sans traitement special, les noms de 4
            #   appels distincts se retrouvaient concatenes en un nom
            #   inexistant (bug prod 2026-08-22 : `fs_readfs_readfs_readfiche_etapes`
            #   avec Gemini demandant 4 appels d'outils).
            # Reglestrangement conservatrices :
            # - `name` est ATOMIQUE : on affecte, jamais on concatene.
            # - `arguments` est un flux JSON : on concatene.
            # - Sans `index` explicite, l'apparition d'un nouveau `name`
            #   non-vide different du precedent signale un nouveau tool_call.
            tc_list = delta.get("tool_calls")
            if isinstance(tc_list, list):
                # Cas Gemini : quand aucun tool_call du chunk n'a d'`index`, on
                # traite tous les elements de la liste comme des appels distincts
                # ranges apres les precedents. Sinon deux `fs_read` successifs
                # sans index seraient vus comme un seul appel.
                sans_index = all(isinstance(tc, dict) and tc.get("index") is None for tc in tc_list)
                base_position = (
                    (max(tool_calls_par_index.keys()) + 1) if tool_calls_par_index else 0
                )
                for position, tc_delta in enumerate(tc_list):
                    if not isinstance(tc_delta, dict):
                        continue
                    fn_delta = tc_delta.get("function") or {}
                    nom_nouveau = fn_delta.get("name") or ""
                    idx = tc_delta.get("index")
                    if idx is None:
                        idx = base_position + position if sans_index else 0
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
                    if nom_nouveau:
                        # Affecter, pas concatener : le nom d'outil est
                        # atomique. Un `+=` ecrase la valeur precedente si le
                        # provider repete le nom, mais surtout empeche le
                        # scenario prod ou 4 noms distincts fusionnaient.
                        existing["function"]["name"] = nom_nouveau
                    if fn_delta.get("arguments"):
                        existing["function"]["arguments"] += fn_delta["arguments"]
                    # Gemini thinking (3.7-flash) signe ses tool_calls avec
                    # `extra_content.google.thought_signature`. Ce champ DOIT
                    # revenir dans le message assistant au tour suivant, sinon
                    # Gemini refuse HTTP 400 « Function call is missing a
                    # thought_signature ». On le preserve ici ; le filtrage
                    # selon le provider destinataire se fait dans
                    # `_nettoyer_messages`.
                    extra = tc_delta.get("extra_content")
                    if isinstance(extra, dict):
                        # Fusion recursive superficielle : plusieurs chunks
                        # peuvent enrichir `extra_content` (rare mais safe).
                        current = existing.get("extra_content")
                        if isinstance(current, dict):
                            current.update(extra)
                        else:
                            existing["extra_content"] = dict(extra)
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
        if attente is None:
            attente = _extraire_retry_after(r.headers.get("retry-after"))
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


def _nettoyer_messages(
    messages: list[dict[str, Any]],
    noms_outils_valides: set[str] | None = None,
    provider_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Ne renvoie au provider que le contrat OpenAI commun.

    Gemini signe ses tool_calls d'un ``extra_content.google.thought_signature``
    ; copie verbatim dans l'historique persiste (l'ancien code bloquant
    renvoyait le message du provider tel quel), ce champ est refuse par les
    providers stricts : Mistral repond 422 ``extra_forbidden`` des le tour
    suivant. Une session ouverte avec un provider doit pouvoir continuer sur
    un autre : on reduit chaque message a role/content/tool_call_id/name et
    chaque tool_call a id/type/function{name, arguments}.

    Si ``noms_outils_valides`` est fourni, les tool_calls dont le ``name`` n'y
    figure pas sont retires (historique corrompu par un ancien bug ou par un
    provider qui a hallucine un nom d'outil). Les messages ``tool`` orphelins
    (qui repondaient a un tool_call retire) sont retires aussi : Gemini refuse
    HTTP 400 « Request contains an invalid argument » sur un `tool` sans son
    `assistant.tool_calls` correspondant. Bug prod 2026-08-22 :
    ``fs_readfs_readfs_readfiche_etapes`` persiste par le bug SSE avant fix,
    puis chaque tour suivant bloquait.
    """
    propres: list[dict[str, Any]] = []
    ids_valides: set[str] = set()
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
                nom = fn.get("name") or ""
                if noms_outils_valides is not None and nom and nom not in noms_outils_valides:
                    # Tool_call orphelin : outil inconnu du provider. Le
                    # rejouer produit HTTP 400.
                    logger.info("tool_call filtre : nom inconnu %r", nom)
                    continue
                tc_id = tc.get("id") or ""
                if tc_id:
                    ids_valides.add(tc_id)
                tc_nettoye: dict[str, Any] = {
                    "id": tc_id,
                    "type": tc.get("type") or "function",
                    "function": {
                        "name": nom,
                        "arguments": fn.get("arguments") or "",
                    },
                }
                # Gemini thinking (3.7-flash) exige que
                # `extra_content.google.thought_signature` revienne au tour
                # suivant, sinon HTTP 400. Les autres providers (Mistral en
                # particulier) refusent ce champ (422 extra_forbidden). On le
                # preserve donc uniquement quand on repart sur Gemini.
                extra = tc.get("extra_content")
                if provider_kind == "gemini" and isinstance(extra, dict):
                    tc_nettoye["extra_content"] = extra
                nettoyes.append(tc_nettoye)
            # Message assistant vide de tool_calls valides ET sans contenu
            # texte : on le drop plutot que d'envoyer un fantome.
            if not nettoyes and not (propre.get("content") or "").strip():
                continue
            if nettoyes:
                propre["tool_calls"] = nettoyes
            else:
                propre.pop("tool_calls", None)
        # Un message `tool` qui repond a un tool_call retire est orphelin :
        # Gemini refuse HTTP 400 sur un tool sans son assistant.tool_calls.
        if (
            propre.get("role") == "tool"
            and noms_outils_valides is not None
            and propre.get("tool_call_id")
            and propre["tool_call_id"] not in ids_valides
        ):
            logger.info("message tool orphelin filtre (tool_call_id inconnu)")
            continue
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
    # Noms d'outils valides pour ce tour : sert a filtrer les tool_calls
    # historiques dont le nom n'existe plus (bug SSE d'avant fix, hallucination
    # provider, evolution du registre).
    noms_valides: set[str] = set()
    for o in outils_api or []:
        if isinstance(o, dict):
            fn_meta = o.get("function")
            if isinstance(fn_meta, dict) and isinstance(fn_meta.get("name"), str):
                noms_valides.add(fn_meta["name"])
    payload = format_chat_payload(
        provider.provider,
        modele or provider.model,
        _nettoyer_messages(messages, noms_valides or None, provider.provider),
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
                        # Jitter ±25 % : evite que plusieurs clients (ou tours
                        # paralleles) se resynchronisent sur le meme instant de
                        # retry et recharge le provider en melee.
                        base = random.uniform(attente * 0.75, attente * 1.25)  # nosec B311 - jitter de backoff non cryptographique
                        logger.info(
                            "HTTP %s sur tour agent (tentative %d/%d), backoff %.0fs",
                            statut_5xx,
                            i + 1,
                            len(_BACKOFF_5XX),
                            base,
                        )
                        await asyncio.sleep(base)
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
    # `default=str` pour la meme raison que dans `_sse` : un champ qui ne sait
    # pas se serialiser doit degrader, pas faire echouer le tour entier.
    contenu = json.dumps(resultat, ensure_ascii=False, default=str)[:TOOL_RESULT_MAX]
    return {"role": "tool", "tool_call_id": tool_call_id, "name": nom, "content": contenu}


def _arguments_de(tool_call: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Rend les arguments d'un appel d'outil, et s'ils étaient lisibles.

    Un flux coupé au milieu des arguments laisse du JSON tronqué. On lisait ça
    comme ``{}`` et on exécutait quand même : le modèle recevait le résultat
    plausible d'un appel qu'il n'avait pas formulé, et le rapportait comme
    fait. Absent n'est pas malformé, et il faut pouvoir les distinguer.
    """
    brut = tool_call.get("function", {}).get("arguments") or ""
    if not brut.strip():
        return {}, True
    try:
        args = json.loads(brut)
    except json.JSONDecodeError:
        return {}, False
    return (args, True) if isinstance(args, dict) else ({}, False)


#: Un appel d'outil prêt à exécuter : (brut du fournisseur, nom, arguments,
#: arguments lisibles ?).
_Appel = tuple[dict[str, Any], str, dict[str, Any], bool]


def _empreinte(nom: str, args: dict[str, Any]) -> str:
    """Ce qui fait qu'un appel est « le même » qu'un autre.

    Les clés sont triées : un fournisseur ne garantit pas l'ordre des champs
    d'un objet JSON, et deux sérialisations du même appel doivent se reconnaître.
    """
    return nom + " " + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)


#: Ce que rend un appel dont l'empreinte a déjà échoué dans la conversation.
#:
#: La règle 5 du prompt système dit déjà de ne pas répéter un appel identique
#: après une erreur. Mesure du 2026-08-30 : elle ne tient pas. Sur une source
#: illisible, le modèle a rejoué six fois le même `add_excerpt`, mot pour mot,
#: avant d'abandonner. Une consigne se contourne en l'ignorant, donc la boucle
#: se casse ici, où le rejeu est simplement impossible.
#:
#: Seuls les échecs sont mémorisés. Un appel qui a réussi peut légitimement être
#: refait, et rien ne dit qu'un outil soit idempotent.
_DEJA_ECHOUE = (
    "Tu as déjà fait cet appel dans cette conversation, avec exactement les "
    "mêmes arguments, et il a échoué. Le rejouer donnerait le même résultat. "
    "Ce qu'il avait répondu : {message} "
    "Change les arguments, prends un autre outil, ou dis au créateur que ce "
    "n'est pas possible. N'annonce pas cette action comme faite."
)


#: Outils qui touchent l'``AsyncSession`` du contexte, donc jamais en parallèle.
#:
#: Strictement plus large que `OUTILS_QUI_ECRIVENT`, qui sert au contrôle des
#: annonces non tenues et ne doit compter que les écritures éditoriales. Les deux
#: ensembles répondent à deux questions différentes, les confondre casserait
#: silencieusement l'un des deux.
OUTILS_NON_PARALLELISABLES: frozenset[str] = OUTILS_QUI_ECRIVENT | OUTILS_OBJECTIF


def _lot_parallelisable(appels: list[_Appel]) -> bool:
    """Le lot d'appels d'un même message assistant peut-il partir ensemble ?

    Les lectures partent ensemble, les écritures restent en file. Deux
    frontières, et aucune n'est négociable :

    - une écriture partage l'``AsyncSession`` du contexte, et ce dépôt interdit
      de partager une session entre coroutines ;
    - une approbation est une interaction humaine séquentielle : deux demandes
      concurrentes apparaîtraient en même temps à l'écran, sans dire laquelle
      répond à quoi.

    Le gain est là malgré tout : les tours lents sont des tours de lecture.
    """
    if len(appels) < 2:
        return False
    return not any(
        nom in OUTILS_NON_PARALLELISABLES or est_sensible(nom, args) for _tc, nom, args, _ in appels
    )


async def _executer_tour(
    db: AsyncSession,
    user: User,
    tour: int,
    messages: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    registre: dict[str, AgentTool],
    emit: Emitter,
    approuver: Approuver,
    session_id: UUID | None = None,
    echecs: dict[str, str] | None = None,
) -> None:
    ctx = ToolContext(db=db, user=user, creator_id=user.id, session_id=session_id)
    if echecs is None:
        echecs = {}
    appels: list[_Appel] = []
    for tc in tool_calls:
        try:
            nom = tc["function"]["name"]
        except (KeyError, TypeError):
            continue
        args, lisibles = _arguments_de(tc)
        # Fallback si le provider a envoyé un tool_call sans id (rare mais
        # possible avec des endpoints custom). L'identifiant est posé ici, une
        # fois pour toutes : le lot entier est annoncé avant que le premier
        # résultat n'arrive, et côté interface un résultat sans identifiant
        # rejoindrait la dernière carte en attente, pas la sienne.
        tc["id"] = tc.get("id") or f"call_{uuid4().hex[:12]}"
        await emit(
            {
                "type": "tool_call",
                "payload": {"id": tc["id"], "name": nom, "arguments": args, "tour": tour},
            }
        )
        appels.append((tc, nom, args, lisibles))

    async def _resoudre(appel: _Appel) -> dict[str, Any]:
        return await _resultat_appel(db, user, tour, appel, registre, ctx, emit, approuver, echecs)

    if _lot_parallelisable(appels):
        resultats = list(await asyncio.gather(*(_resoudre(a) for a in appels)))
    else:
        resultats = [await _resoudre(a) for a in appels]

    # L'ordre rendu est celui des `tool_calls`, jamais l'ordre d'arrivée des
    # résultats : un lot désordonné casse la correspondance chez certains
    # fournisseurs, et affiche les cartes d'outil en désordre à l'écran.
    for (tc, nom, _args, _lisibles), resultat in zip(appels, resultats, strict=True):
        await emit(
            {
                "type": "tool_result",
                "payload": {"id": tc["id"], "name": nom, "result": resultat},
            }
        )
        messages.append(_message_tool(tc["id"], nom, resultat))


async def _resultat_appel(
    db: AsyncSession,
    user: User,
    tour: int,
    appel: _Appel,
    registre: dict[str, AgentTool],
    ctx: ToolContext,
    emit: Emitter,
    approuver: Approuver,
    echecs: dict[str, str],
) -> dict[str, Any]:
    """Un appel d'outil, de ses arguments à son résultat, borné dans le temps."""
    _tc, nom, args, lisibles = appel
    if not lisibles:
        return {
            "error": (
                "Arguments illisibles : le JSON reçu est incomplet ou malformé, "
                "probablement une réponse tronquée. Refais l'appel avec des "
                "arguments complets. N'annonce pas cette action comme faite."
            )
        }
    # Avant l'approbation, pas après : redemander à la personne de valider une
    # écriture dont on sait déjà qu'elle échouera lui ferait garder une boucle
    # que ce garde-fou existe pour lui épargner.
    empreinte = _empreinte(nom, args)
    if empreinte in echecs:
        return {"error": _DEJA_ECHOUE.format(message=echecs[empreinte])}
    approbation = False
    if est_sensible(nom, args):
        request_id = str(uuid4())
        resume = await _resume_approbation(db, user, nom, args)
        await emit(
            {
                "type": "approval_request",
                "payload": {
                    "request_id": request_id,
                    "tool": nom,
                    "arguments": args,
                    "resume": resume,
                    "tour": tour,
                    "expires_at": time.time() + DELAI_APPROBATION,
                },
            }
        )
        approbation = await approuver(request_id, nom, args)
        await emit(
            {
                "type": "approval_resolved",
                "payload": {"request_id": request_id, "tool": nom, "approved": approbation},
            }
        )
        if not approbation:
            return {"error": "Action refusée : l'utilisateur n'a pas validé cette écriture."}
    budget = TIMEOUTS_PAR_OUTIL.get(nom, TIMEOUT_OUTIL)
    try:
        resultat = await asyncio.wait_for(
            executer(registre, nom, args, ctx, approbation_obtenue=approbation),
            timeout=budget,
        )
    except TimeoutError:
        resultat = {
            "error": (
                f"{nom} n'a pas répondu en {budget:.0f} secondes et a été "
                "interrompu. Les autres appels de ce tour ont abouti. "
                "N'annonce pas cette action comme faite."
            )
        }
    # Le refus d'approbation n'arrive pas ici, et c'est voulu : il est rendu
    # plus haut. La personne a le droit de refuser puis d'accepter, mémoriser
    # son refus lui retirerait ce droit.
    erreur = resultat.get("error") if isinstance(resultat, dict) else None
    if erreur:
        echecs[empreinte] = str(erreur)
    return resultat


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
    agent_def: AgentDefinition | None = None,
    ancre_tokens: tuple[int, int] | None = None,
    session_id: UUID | None = None,
) -> None:
    """Exécute la boucle jusqu'à ``done`` ou à la borne dure.

    ``messages`` est muté : le prompt système est inséré en tête, puis chaque
    tour ajoute l'assistant et les résultats d'outils. L'appelant fournit
    ``approuver`` (Phase 3 : refus par défaut, Phase 4 : approbation humaine
    réelle) et ``transport`` pour les tests.

    ``agent_def`` restreint les outils visibles et le contexte injecté. Sans
    lui, tous les outils et tout `shared/` partent au modèle.

    ``ancre_tokens`` est le ``(messages couverts, prompt_tokens)`` du dernier
    appel de la session, tel que rendu par
    :func:`agent_sessions.ancre_du_dernier_appel`. Sans lui, la compaction
    préventive du premier appel d'un tour retombe sur l'estimation.

    ``session_id`` donne aux outils d'objectif la ligne qu'ils annotent, et fait
    remonter l'objectif déjà posé dans le prompt système. Sans lui, la boucle
    tourne comme avant : les deux outils répondent qu'ils n'ont pas de session.
    """
    registre = registre or construire_registre()
    if agent_def is not None:
        registre = filtrer(registre, agent_def.tools)
    outils_api = registre_api(registre)
    workspace_ctx = await _priming_workspace(
        db, user.id, agent_def.context if agent_def is not None else None
    )
    systeme = _contexte_temporel() + _SYSTEME + await _contexte_objectif(db, user.id, session_id)
    if agent_def is not None:
        systeme += f"\n\n---\n## Ton rôle : {agent_def.name}\n{agent_def.system_prompt.strip()}\n"
    # Graphe memoire : 3 tables, 1 requete recursive. Le parcours est fait en SQL
    # avant l'appel, donc zero appel d'outil et zero saut par le modele.
    graph_ctx = ""
    try:
        from app.services.graph_memory import recall as graph_recall

        q = next(
            (
                m["content"]
                for m in reversed(messages)
                if m.get("role") == "user" and isinstance(m.get("content"), str)
            ),
            "",
        )
        if q:
            # `top_k` borne le contexte injecte. Il etait laisse a son defaut,
            # et l'entete annoncait « 2 ms » en dur alors que `Facts.ms` porte la
            # mesure : deux facons de dire au modele quelque chose de faux sur ce
            # qu'il vient de recevoir.
            facts = await graph_recall(db, q, hops=3, top_k=_GRAPHE_FAITS_MAX)
            if facts.triples:
                graph_ctx = "\n\n---\n## Mémoire graphe (rappel automatique)\n" + facts.as_text()
                if len(facts.triples) == _GRAPHE_FAITS_MAX:
                    graph_ctx += (
                        f"\n\n(rappel borné à {_GRAPHE_FAITS_MAX} faits : "
                        "le graphe peut en porter d'autres sur cette question, "
                        "utilisez recall_memory pour aller plus loin)"
                    )
                graph_ctx += "\n"
    except Exception:  # nosec B110
        pass
    messages.insert(0, {"role": "system", "content": systeme + workspace_ctx + graph_ctx})

    meter = TokenMeter()
    if ancre_tokens is not None:
        # L'ancre vient de l'historique persisté, qui ne porte pas le prompt
        # système. Il vient d'être inséré en tête, et il était là aussi lors de
        # l'appel mesuré : le préfixe couvert avance donc d'exactement un.
        couverts, tokens_reels = ancre_tokens
        meter.ancrer(messages[: couverts + 1], tokens_reels)

    # Compaction préventive, prompt système et contexte workspace compris : ce
    # sont eux qui pèsent le plus lourd au départ d'une session.
    compaction = compacter(messages, BUDGET_HISTORIQUE, meter)
    # Compteur du seul rejeu réactif : la passe préventive ci-dessus ne doit pas
    # le consommer, sinon un refus survenant plus tard dans la même session ne
    # serait plus rattrapé.
    rejeu_fait = False
    if compaction.retires or compaction.elagues:
        messages[:] = compaction.messages
        await emit(
            {
                "type": "contexte_compacte",
                "payload": {
                    "messages_retires": compaction.retires,
                    "resultats_elagues": compaction.elagues,
                },
            }
        )

    usage_total: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def _boucler() -> None:
        nonlocal rejeu_fait
        # Utiliser le quota_tours si défini dans agent_def, sinon utiliser MAX_TOURS
        quota_tours = agent_def.quota_tours if agent_def else MAX_TOURS
        a_ecrit = False
        relance_faite = False
        # Vit sur toute la boucle, pas sur un tour : la répétition observée en
        # production enjambe les tours, le modèle relit l'erreur puis refait le
        # même appel au tour suivant.
        echecs: dict[str, str] = {}
        for tour in range(1, quota_tours + 1):

            async def _on_delta(content: str, _t: int = tour) -> None:
                await emit({"type": "message_delta", "payload": {"delta": content, "tour": _t}})

            reponse = await _appel_provider(
                provider, messages, outils_api, transport, on_delta=_on_delta, modele=modele
            )
            if isinstance(reponse, str):
                # Le budget préventif est un pari : le fournisseur, lui, connaît
                # sa fenêtre. Quand il refuse pour cette raison, on le croit et
                # on retente une fois, beaucoup plus bas. Une seule fois : deux
                # refus de suite ne viennent plus de la taille.
                if not rejeu_fait and _est_contexte_sature(reponse):
                    reduction = compacter(messages, BUDGET_APRES_REFUS, meter)
                    rejeu_fait = True
                    if reduction.retires or reduction.elagues:
                        messages[:] = reduction.messages
                        await emit(
                            {
                                "type": "contexte_compacte",
                                "payload": {
                                    "messages_retires": reduction.retires,
                                    "resultats_elagues": reduction.elagues,
                                },
                            }
                        )
                        continue
                await emit({"type": "error", "payload": {"message": reponse}})
                return
            message, finish_reason, usage = reponse
            if isinstance(usage, dict):
                usage_total["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                usage_total["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                # ``messages`` est encore exactement ce que le fournisseur a lu :
                # l'assistant de ce tour n'est ajouté que plus bas.
                meter.ancrer(messages, int(usage.get("prompt_tokens") or 0))
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                texte = _texte_message(message)
                if texte:
                    if not a_ecrit and not relance_faite and _ANNONCE_FAITE.search(texte):
                        relance_faite = True
                        messages.append({"role": "assistant", "content": texte})
                        messages.append({"role": "system", "content": _CONTROLE_RELANCE})
                        await emit({"type": "controle_relance", "payload": {"tour": tour}})
                        continue
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
            if any(
                (tc.get("function") or {}).get("name") in OUTILS_QUI_ECRIVENT for tc in tool_calls
            ):
                a_ecrit = True
            messages.append(
                {
                    "role": "assistant",
                    "content": _texte_message(message) or None,
                    "tool_calls": tool_calls,
                }
            )
            await _executer_tour(
                db, user, tour, messages, tool_calls, registre, emit, approuver, session_id, echecs
            )
        # Limite atteinte : pas une erreur dure, mais une pause avec reprise.
        # Les harness modernes (cordis, opencode) n'ont pas de compteur dur :
        # seule la fenêtre contexte compte. On compacte et on propose de continuer.
        pause = compacter(messages, BUDGET_APRES_REFUS, meter)
        if pause.retires or pause.elagues:
            messages[:] = pause.messages
            await emit(
                {
                    "type": "contexte_compacte",
                    "payload": {
                        "messages_retires": pause.retires,
                        "resultats_elagues": pause.elagues,
                    },
                }
            )
        await emit(
            {
                "type": "continuation",
                "payload": {
                    "message": f'Pause après {MAX_TOURS} actions : l\'agent a beaucoup travaillé et peut continuer. Cliquez sur Continuer ou envoyez "continue".',
                    "tours": MAX_TOURS,
                },
            }
        )

    try:
        await asyncio.wait_for(_boucler(), timeout=BOUCLE_TIMEOUT)
    except asyncio.CancelledError:
        # Annulation propre (disconnect SSE, arrêt serveur) : pas une erreur.
        await emit({"type": "error", "payload": {"message": "Communication interrompue."}})
        raise
    except TimeoutError:
        logger.warning("Boucle de l'agent pour %s dépassée (%ss)", user.id, BOUCLE_TIMEOUT)
        await emit(
            {
                "type": "error",
                "payload": {"message": "L'agent a mis trop de temps à répondre. Réessayez."},
            }
        )
    except Exception as exc:  # noqa: BLE001 -- un échec de boucle doit être visible, pas silencieux
        logger.exception("Échec de la boucle de l'agent pour %s", user.id)
        await emit({"type": "error", "payload": {"message": f"Erreur interne de l'agent : {exc}"}})
