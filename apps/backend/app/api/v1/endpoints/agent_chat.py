"""Endpoint chat de l'agent BYOK : un message, un flux SSE.

Le client envoie ``{message, history?, session_id?}`` ; le serveur rend un flux
d'événements (``text/event-stream``) produits par la boucle de l'agent :

- ``session`` : l'identifiant de la session, émis en tête (créée si absente) ;
- ``message_delta`` : un bout de la réponse finale du modèle ;
- ``tool_call`` / ``tool_result`` : un outil exécuté et son résultat ;
- ``approval_request`` / ``approval_resolved`` : une action sensible soumise
  à validation humaine, puis sa résolution ;
- ``done`` (motif ``complete``) : fin normale ;
- ``error`` : erreur provider ou borne atteinte.

Avec une session, l'historique vient de la base et le tour y est écrit en
append-only. L'approbation suspend réellement la boucle : elle attend
``POST /agent/approve`` et refuse au bout de ``agent_approvals.DELAI_MAX``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.agent_providers import get_http_client
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import async_session_maker, get_db
from app.models.user import User
from app.schemas.agent_chat import AgentChatRequest
from app.services import agent_approvals, agent_definitions, agent_gratuit, agent_sessions
from app.services.agent import boucle
from app.services.agent_discovery import (
    ErreurQuota,
    consommer_message,
    discovery_est_actif,
    nom_public_provider,
    resoudre_provider_decouverte,
    verifier_quota,
)
from app.services.agent_providers import obtenir_pour_chat, resoudre_defaut

#: Chaines detectees pour poser un cooldown de lane apres un echec fournisseur.
#: Les erreurs provider arrivent deja traduites par la couche LLM (« refuse :
#: quota ou limite de débit », « HTTP 500 ») : on matche le francais ET le brut.
_MARQUEURS_RATE_LIMIT = (
    "429",
    "rate limit",
    "quota",
    "débit",
    "debit",
    "surcharge",
    "overloaded",
    "insufficient",
    "http 5",
)

#: Message remplace a l'utilisateur quand la lane gratuite echoue : l'erreur
#: technique brute (« Le fournisseur (zai) refuse... ») ne dit rien d'actionnable.
_MESSAGE_SURCHARGE_GRATUIT = (
    "Le fournisseur gratuit est momentanément indisponible "
    "(surcharge côté fournisseur). Réessayez dans quelques minutes, "
    "ou connectez votre clé depuis la page Clés pour reprendre immédiatement."
)


def _echec_fournisseur_gratuit(texte: str) -> bool:
    return any(m in texte.lower() for m in _MARQUEURS_RATE_LIMIT)


settings = get_settings()

router = APIRouter(prefix="/agent", tags=["agent-chat"])


def get_approver():
    """Fabrique le callback d'approbation. Surchargeable en test.

    Rend une fonction qui, pour un ``creator_id``, suspend la boucle jusqu'à
    la réponse humaine via ``POST /agent/approve``.
    """

    def pour(creator_id):
        async def approuver(request_id: str, tool: str, args: dict[str, Any]) -> bool:
            return await agent_approvals.attendre(request_id, creator_id)

        return approuver

    return pour


def _sse(event: dict[str, Any]) -> str:
    """Un evenement SSE. `default=str` n'est pas une commodite, c'est un fusible.

    Le resultat d'un outil part tel quel dans le flux. `fs_list` rendait un
    `datetime` brut : `json.dumps` levait, le generateur mourait au milieu du
    stream, et la conversation restait figee sur « En cours… » sans qu'aucune
    erreur n'atteigne l'utilisateur. Un champ mal type doit degrader ce champ,
    jamais interrompre le tour.
    """
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat_agent(
    request: Request,
    body: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    transport: httpx.AsyncBaseTransport | None = Depends(get_http_client),
    fabrique_approbation=Depends(get_approver),
):
    if body.session_id is None:
        session = await agent_sessions.creer(
            db,
            current_user.id,
            title=agent_sessions.titre_depuis_message(body.message),
            agent_slug=body.agent_slug,
        )
        messages: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in body.history
        ]
        # Session neuve : aucun appel mesuré, donc rien à quoi s'ancrer.
        ancre_tokens: tuple[int, int] | None = None
    else:
        try:
            session = await agent_sessions.obtenir(db, current_user.id, body.session_id)
        except agent_sessions.AgentSessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "session_not_found", "message": str(exc)},
            ) from exc
        # L'historique persisté fait autorité : ce que le client renvoie
        # pourrait avoir été retouché en route.
        messages = await agent_sessions.historique_pour_modele(db, current_user.id, session.id)
        # Le dernier compte de tokens du fournisseur sur cette session : il
        # rend la compaction préventive juste dès le premier appel du tour.
        ancre_tokens = await agent_sessions.ancre_du_dernier_appel(db, current_user.id, session.id)

    # Changer d'agent en cours de conversation vaut pour la suite : la session
    # porte le dernier choix, le client n'a pas a le repeter a chaque message.
    # Ecrit sans commit propre, le message utilisateur juste apres le persiste.
    if body.agent_slug:
        session.agent_slug = body.agent_slug
    # Un slug qui ne resout rien (fichier supprime, renomme) degrade vers le
    # generaliste plutot que de casser la conversation.
    agent_def = await agent_definitions.obtenir(
        db, current_user.id, session.agent_slug or agent_definitions.SLUG_DEFAUT
    )

    # Provider explicite du corps de la requete, sinon mode gratuite consenti,
    # sinon provider par defaut, sinon decouverte.
    provider = None
    if body.provider_id:
        provider = await obtenir_pour_chat(db, current_user.id, body.provider_id)
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "provider_not_found", "message": "Cle provider introuvable."},
            )
    mode_gratuit: agent_gratuit.LaneActive | None = None
    mode_decouverte = False
    remaining_today: int | None = None
    if provider is None and await agent_gratuit.est_consentant(db, current_user.id):
        lane_active = await agent_gratuit.choisir_lane(db)
        try:
            remaining_today = await agent_gratuit.verifier_quota_utilisateur(db, current_user.id)
        except agent_gratuit.ErreurQuotaGratuit as exc:
            quota_msg = (
                f"Vous avez atteint la limite de {exc.quota} messages par jour en mode "
                "gratuit. Reessayez demain ou connectez votre propre cle pour continuer "
                "sans limite."
            )
            erreur = {"type": "error", "payload": {"message": quota_msg}}
            return StreamingResponse(
                iter(
                    [
                        _sse({"type": "session", "payload": {"id": str(session.id)}}),
                        _sse(erreur),
                    ]
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        if lane_active is not None:
            provider = lane_active.provider
            mode_gratuit = lane_active
            # Le tour est consomme a l'arrivee : un tour qui echoue a mi-course
            # a quand meme mobilise la lane.
            await agent_gratuit.consommer_requete(db, lane_active.lane)
    if provider is None:
        provider = await resoudre_defaut(db, current_user.id)
    if provider is None:
        if discovery_est_actif():
            try:
                remaining_today = await verifier_quota(db, current_user.id)
            except ErreurQuota as exc:
                quota_msg = (
                    f"Vous avez atteint la limite de {exc.quota} messages par jour "
                    "en mode decouverte. Connectez votre propre cle pour continuer "
                    "sans limite. Providers gratuits : Mistral, Google AI Studio, "
                    "Groq, Cerebras."
                )
                erreur = {"type": "error", "payload": {"message": quota_msg}}
                return StreamingResponse(
                    iter(
                        [
                            _sse({"type": "session", "payload": {"id": str(session.id)}}),
                            _sse(erreur),
                        ]
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
            provider = resoudre_provider_decouverte()
            mode_decouverte = True
        else:
            erreur = {
                "type": "error",
                "payload": {
                    "message": "Aucune clé IA disponible. Enregistrez-en une dans Agent > Clés, "
                    "ou activez le mode gratuit si cette instance en propose un."
                },
            }
            return StreamingResponse(
                iter(
                    [
                        _sse({"type": "session", "payload": {"id": str(session.id)}}),
                        _sse(erreur),
                    ]
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    messages.append({"role": "user", "content": body.message})
    await agent_sessions.ajouter_message(db, session, role="user", content=body.message)
    # `boucle` insère le prompt système en tête : le tour commence donc un cran
    # plus loin que la longueur d'avant l'appel.
    depart = len(messages) + 1
    approuver = fabrique_approbation(current_user.id)

    async def gen():
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        reponse_finale: list[str] = []
        usage_capture: list[dict[str, Any]] = []

        async def emit(event: dict[str, Any]) -> None:
            if event.get("type") == "message_delta":
                reponse_finale.append(event["payload"]["delta"])
            elif event.get("type") == "done":
                u = event.get("payload", {}).get("usage")
                if isinstance(u, dict):
                    usage_capture.append(u)
            await queue.put(event)

        # `boucle` ne leve PAS d'exception sur une erreur provider : elle emet
        # un evenement `error` puis retourne normalement. On surveille donc
        # l'emission pour poser le cooldown et traduire l'erreur en message
        # actionnable ; le except ci-dessous reste pour les vraies levées.
        echecs_gratuit: list[str] = []

        async def emit_surveille(event: dict[str, Any]) -> None:
            if mode_gratuit is not None and event.get("type") == "error":
                texte = str(event.get("payload", {}).get("message", ""))
                if _echec_fournisseur_gratuit(texte):
                    echecs_gratuit.append(texte)
                    event = {
                        **event,
                        "payload": {"message": _MESSAGE_SURCHARGE_GRATUIT},
                    }
            await emit(event)

        async def runner() -> None:
            try:
                await boucle(
                    db,
                    current_user,
                    provider,
                    messages,
                    emit_surveille,
                    approuver,
                    transport=transport,
                    modele=body.model_override or session.model_override or None,
                    agent_def=agent_def,
                    ancre_tokens=ancre_tokens,
                )
                if echecs_gratuit and mode_gratuit is not None:
                    with contextlib.suppress(Exception):
                        await agent_gratuit.signaler_echec(db, mode_gratuit.lane)
            except Exception as exc:
                # Un 429/quota provider en pleine conversation : la lane prend
                # un cooldown, le prochain tour partira sur une autre lane.
                if mode_gratuit is not None and _echec_fournisseur_gratuit(str(exc)):
                    # Best-effort : si la session DB est deja fermee (client
                    # parti), tant pis, le cooldown ratera ce tour-ci.
                    with contextlib.suppress(Exception):
                        await agent_gratuit.signaler_echec(db, mode_gratuit.lane)
                raise
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())
        yield _sse({"type": "session", "payload": {"id": str(session.id)}})
        if mode_decouverte:
            yield _sse(
                {
                    "type": "discovery_active",
                    "payload": {
                        "provider_public_name": nom_public_provider(),
                        "remaining_today": remaining_today,
                        "retention_notice": "Ce provider peut utiliser vos echanges pour ameliorer son modele.",
                    },
                }
            )
        if mode_gratuit is not None:
            yield _sse(
                {
                    "type": "gratuit_actif",
                    "payload": {
                        "provider_public_name": mode_gratuit.lane.label_public,
                        "remaining_today": remaining_today,
                        "retention_notice": (
                            "Ce fournisseur gratuit peut conserver vos echanges et les "
                            "utiliser pour entrainer ses modeles."
                        ),
                    },
                }
            )
        # Sans ce `finally`, un client qui ferme l'onglet laisse la boucle
        # tourner jusqu'a 24 tours : elle continue de facturer le provider et
        # d'ecrire via une session de base que FastAPI a deja fermee.
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse(event)
            await task
            usage = usage_capture[0] if usage_capture else None
            # Session de base dédiée : pas la session FastAPI (`db`), qui peut
            # être fermée quand l'utilisateur a quitté avant la fin du flux.
            await _persister_tour(
                current_user.id, session.id, messages[depart:], "".join(reponse_finale), usage
            )
            if mode_gratuit is not None:
                async with async_session_maker() as db_dedie:
                    await agent_gratuit.consommer_message_utilisateur(db_dedie, current_user.id)
            elif mode_decouverte:
                async with async_session_maker() as db_dedie:
                    await consommer_message(db_dedie, current_user.id)
        finally:
            task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _persister_tour(
    creator_id: UUID,
    session_id: UUID,
    ajouts: list[dict[str, Any]],
    reponse_finale: str,
    usage: dict[str, Any] | None = None,
) -> None:
    """Ecrit le tour en base, append-only, dans l'ordre ou il s'est produit.

    La reponse textuelle finale n'est pas dans ``messages`` : la boucle
    l'emet en ``message_delta`` sans la rajouter a l'historique. On la
    recompose ici pour que le tour suivant la voie.

    Ouvre sa propre session de base, independante de celle injectee par
    FastAPI : le tour est persiste apres la fin du flux SSE, quand la session
    du middleware peut deja etre fermee (client parti, timeout du serveur).
    """
    async with async_session_maker() as db:
        session = await agent_sessions.obtenir(db, creator_id, session_id)
        for message in ajouts:
            if message.get("role") == "tool":
                await agent_sessions.ajouter_message(
                    db,
                    session,
                    role="tool",
                    content=message.get("content") or "",
                    tool_name=message.get("name"),
                    tool_call_id=message.get("tool_call_id"),
                )
            else:
                await agent_sessions.ajouter_message(
                    db,
                    session,
                    role=message.get("role") or "assistant",
                    content=message.get("content") or "",
                    tool_calls=message.get("tool_calls"),
                )
        if reponse_finale:
            prompt_tokens: int | None = None
            completion_tokens: int | None = None
            if isinstance(usage, dict):
                v = usage.get("prompt_tokens")
                prompt_tokens = v if isinstance(v, int) and v > 0 else None
                v = usage.get("completion_tokens")
                completion_tokens = v if isinstance(v, int) and v > 0 else None
            await agent_sessions.ajouter_message(
                db,
                session,
                role="assistant",
                content=reponse_finale,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
