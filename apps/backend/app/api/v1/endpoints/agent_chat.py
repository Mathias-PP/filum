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

Le tour tourne dans une tache detachee de la connexion (`agent_tours`) : un
client coupe le rattrape par ``GET /agent/sessions/{id}/flux?depuis=N``, et
seul ``POST /agent/sessions/{id}/arreter`` l'arrete.

Avec une session, l'historique vient de la base et le tour y est écrit en
append-only. L'approbation suspend réellement la boucle : elle attend
``POST /agent/approve`` et refuse au bout de ``agent_approvals.DELAI_MAX``.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import anyio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.agent_providers import get_http_client
from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.database import async_session_maker, get_db
from app.models.agent_provider import AgentProvider
from app.models.user import User
from app.schemas.agent_chat import AgentChatRequest
from app.services import (
    agent_approvals,
    agent_definitions,
    agent_gratuit,
    agent_sessions,
    agent_tours,
    agent_workspace,
    deroule_guide,
)
from app.services.agent_discovery import (
    ErreurQuota,
    consommer_message,
    discovery_est_actif,
    nom_public_provider,
    resoudre_provider_decouverte,
    verifier_quota,
)
from app.services.agent_providers import obtenir_pour_chat, ordonner_pour_chat, resoudre_defaut
from app.services.options_recherche import OPTIONS_RECHERCHE, Options, options_demandees

#: Message remplace a l'utilisateur quand la lane gratuite echoue : l'erreur
#: technique brute (« Le fournisseur (zai) refuse... ») ne dit rien d'actionnable.
_MESSAGE_SURCHARGE_GRATUIT = (
    "Le fournisseur gratuit est momentanément indisponible "
    "(surcharge côté fournisseur). Réessayez dans quelques minutes, "
    "ou connectez votre clé depuis la page Clés pour reprendre immédiatement."
)

#: Distinct du precedent : aucun delai ne repare une cle refusee, et inviter le
#: createur a « réessayer dans quelques minutes » l'enverrait attendre pour rien.
_MESSAGE_CLE_GRATUITE_REFUSEE = (
    "Le mode gratuit est indisponible : la clé du service est refusée par le "
    "fournisseur. Ce n'est pas un pic de charge, réessayer n'y changera rien. "
    "Connectez votre clé depuis la page Clés, et signalez le problème."
)


settings = get_settings()

router = APIRouter(prefix="/agent", tags=["agent-chat"])

logger = logging.getLogger(__name__)

#: Evenements qui closent un tour. Publies seulement une fois le tour ecrit en base.
_TERMINAUX = frozenset({"done", "error", "continuation"})

_ENTETES_SSE = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


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


def get_attente():
    """Fabrique l'attente des réponses aux questions du déroulé. Surchargeable en test."""

    def pour(creator_id):
        async def attendre(request_id: str) -> dict[str, Any] | None:
            return await agent_approvals.attendre_reponse(request_id, creator_id)

        return attendre

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
    fabrique_attente=Depends(get_attente),
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
        if agent_tours.en_cours(session.id):
            raise _conflit_tour()
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
    lanes_gratuites: list[agent_gratuit.LaneActive] = []
    if provider is None and await agent_gratuit.est_consentant(db, current_user.id):
        lanes_gratuites = await agent_gratuit.lanes_eligibles(db)
        lane_active = lanes_gratuites[0] if lanes_gratuites else None
        # Plus de plafond par utilisateur en mode gratuit. Celui de 30 messages
        # par jour ne comptait qu'un tour termine page ouverte : 9 messages
        # envoyes le 2026-08-30, 1 seul decompte. Il ne protegeait donc rien, et
        # le nombre choisi n'avait aucune mesure derriere lui. Ce qui protege
        # vraiment le fournisseur reste en place : les plafonds par minute et
        # par jour de chaque lane, et le cooldown apres un 429.
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
                await verifier_quota(db, current_user.id)
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

    # Les cles de repli, dans l'ordre ou les essayer. Un createur qui en a
    # configure trois n'en voyait essayer qu'une.
    replis: list[AgentProvider] = []
    if mode_gratuit is not None:
        # Le cooldown de lane ne repare que le tour suivant : sans repli ici,
        # une saturation du primaire rendait une erreur alors que la lane de
        # secours pouvait repondre tout de suite.
        replis = [candidate.provider for candidate in lanes_gratuites]
    elif not mode_decouverte:
        # Le mode decouverte n'expose qu'une cle, qu'on ne choisit pas.
        replis = await ordonner_pour_chat(db, current_user.id, prefere=provider.id)

    # Une suite proposee sous un bilan prolonge la fiche : elle part droit dans le
    # deroule guide, cible sur sa sous-question. Tout autre message ouvre la
    # conversation, et c'est l'agent qui confie une question au deroule quand
    # elle appelle une fiche (`converser_ou_derouler`), dans toutes les langues.
    guide = body.approfondir is not None
    options = (
        options_demandees(body.recherche.mode, body.recherche.sources, body.recherche.priorite)
        if body.recherche
        else Options()
    )
    suite = (
        deroule_guide.Suite(body.approfondir.card_slug, body.approfondir.sous_question)
        if body.approfondir
        else None
    )

    # Reserve avant toute ecriture : un second envoi pendant qu'un tour tourne
    # reinscrivait le message, et le modele recevait deux fois la meme demande.
    try:
        tour = agent_tours.reserver(session.id, current_user.id)
    except agent_tours.TourEnCoursError as exc:
        raise _conflit_tour() from exc

    try:
        messages.append({"role": "user", "content": body.message})
        await agent_sessions.ajouter_message(db, session, role="user", content=body.message)
        # Le workspace n'etait amorce qu'en ouvrant la page Workspace ou la page
        # Agents. Un createur qui va droit au chat n'y passe jamais : `shared/`
        # restait vide et l'agent ecrivait du contenu editorial sans avoir lu la
        # ligne qui devait le guider.
        #
        # Ici et pas dans `boucle` : la boucle tourne pendant le flux SSE, et une
        # ecriture ouverte pendant tout le flux garde le verrou d'ecriture SQLite,
        # ce qui fait echouer la persistance du tour en « database is locked ».
        # A cet endroit la transaction se ferme avant que le flux commence.
        await agent_workspace.assurer_workspace(db, current_user.id)
        await db.commit()
    except BaseException:
        agent_tours.liberer(tour)
        raise
    # `boucle` insère le prompt système en tête : le tour commence donc un cran
    # plus loin que la longueur d'avant l'appel.
    depart = len(messages) + 1
    approuver = fabrique_approbation(current_user.id)
    attendre = fabrique_attente(current_user.id)
    # Valeurs lues maintenant : la session de base de la requete se ferme avec
    # elle, et le tour lui survit.
    creator_id = current_user.id
    session_id = session.id
    modele = body.model_override or session.model_override or None

    if mode_decouverte:
        tour.publier(
            {
                "type": "discovery_active",
                "payload": {
                    "provider_public_name": nom_public_provider(),
                    "retention_notice": "Ce provider peut utiliser vos echanges pour ameliorer son modele.",
                },
            }
        )
    if mode_gratuit is not None:
        tour.publier(
            {
                "type": "gratuit_actif",
                "payload": {
                    "provider_public_name": mode_gratuit.lane.label_public,
                    "retention_notice": (
                        "Ce fournisseur gratuit peut conserver vos echanges et les "
                        "utiliser pour entrainer ses modeles."
                    ),
                },
            }
        )

    async def travail(publier: agent_tours.Publier) -> None:
        deltas: dict[int, list[str]] = {}
        usage_capture: list[dict[str, Any]] = []
        # Retenus jusqu'a la persistance : un client qui voit `done` peut
        # renvoyer aussitot, et il doit alors trouver le tour ecrit et libre.
        terminaux: list[dict[str, Any]] = []
        # `boucle` ne leve PAS d'exception sur une erreur provider : elle emet
        # un evenement `error` puis retourne normalement. On surveille donc
        # l'emission pour poser le cooldown et traduire l'erreur en message
        # actionnable ; le except ci-dessous reste pour les vraies levées.
        reactions: list[agent_gratuit.Reaction] = []
        issue = "annule"
        # Le deroule guide ne passe pas par `messages` : chaque etape a le sien.
        ajouts_guides: list[dict[str, Any]] = []
        heures_guides: list[datetime] = []
        # La reponse du bilan une fois ses renvois verifies et changes en liens :
        # c'est elle qui s'ecrit en base, pas le texte brut diffuse en direct.
        reponse_verifiee: list[str] = []
        # Le mode et les sources valent pour tout le tour, outils compris.
        OPTIONS_RECHERCHE.set(options)

        # L'heure a laquelle chaque message du tour est apparu. Le tour s'ecrit
        # en base a la fin : sans elles, tous ses messages portaient l'heure de
        # fin (09:02:14 a 09:02:24 pour un tour commence a 08:57).
        horodatages: list[datetime] = []

        def horodater() -> None:
            maintenant = datetime.now(UTC).replace(tzinfo=None)
            while len(horodatages) < len(messages):
                horodatages.append(maintenant)

        async def emit(event: dict[str, Any]) -> None:
            horodater()
            genre = event.get("type")
            if genre == "message_delta":
                charge = event["payload"]
                deltas.setdefault(int(charge.get("tour") or 0), []).append(charge["delta"])
            elif genre == "reponse_verifiee":
                texte_lie = event.get("payload", {}).get("texte")
                if isinstance(texte_lie, str) and texte_lie:
                    reponse_verifiee.append(texte_lie)
            elif genre in ("done", "continuation"):
                u = event.get("payload", {}).get("usage")
                if isinstance(u, dict):
                    usage_capture.append(u)
            elif genre == "error" and mode_gratuit is not None:
                charge = event.get("payload", {})
                statut = charge.get("statut")
                reaction = agent_gratuit.reagir(
                    statut if isinstance(statut, int) else None,
                    str(charge.get("message", "")),
                )
                if reaction.cooldown_minutes is not None:
                    reactions.append(reaction)
                    event = {
                        **event,
                        "payload": {
                            "message": _MESSAGE_CLE_GRATUITE_REFUSEE
                            if reaction.cle_refusee
                            else _MESSAGE_SURCHARGE_GRATUIT
                        },
                    }
            if genre in _TERMINAUX:
                terminaux.append(event)
            else:
                publier(event)

        async with async_session_maker() as db_tour:
            try:
                utilisateur = await db_tour.get(User, creator_id)
                if utilisateur is None:
                    raise RuntimeError("Utilisateur introuvable pour ce tour.")
                if guide:
                    await deroule_guide.derouler(
                        db_tour,
                        utilisateur,
                        provider,
                        body.message,
                        emit,
                        approuver,
                        ajouts_guides,
                        heures_guides,
                        transport=transport,
                        modele=modele,
                        session_id=session_id,
                        replis=replis,
                        options=options,
                        suite=suite,
                        attendre=attendre,
                    )
                else:
                    await deroule_guide.converser_ou_derouler(
                        db_tour,
                        utilisateur,
                        provider,
                        messages,
                        emit,
                        approuver,
                        ajouts_guides,
                        heures_guides,
                        transport=transport,
                        modele=modele,
                        agent_def=agent_def,
                        ancre_tokens=ancre_tokens,
                        session_id=session_id,
                        replis=replis,
                        options=options,
                        attendre=attendre,
                    )
                issue = "complet"
                if reactions and mode_gratuit is not None:
                    # Le repos le plus long l'emporte : si un tour a vu passer
                    # une cle refusee, l'oublier au profit d'un simple pic de
                    # charge remettrait la lane en service dans dix minutes.
                    minutes = max(
                        r.cooldown_minutes for r in reactions if r.cooldown_minutes is not None
                    )
                    with contextlib.suppress(Exception):
                        await agent_gratuit.signaler_echec(db_tour, mode_gratuit.lane, minutes)
            except Exception as exc:  # noqa: BLE001  # le tour doit se clore et se dire
                issue = "echec"
                logger.exception("Tour de l'agent en echec sur la session %s", session_id)
                # Une exception a traverse : le statut HTTP n'a pas survecu, il
                # ne reste que le message. `reagir` refuse de mettre une lane au
                # repos sur un texte qu'il ne reconnait pas, ce qui evite qu'un
                # bug de Philum passe pour une panne du fournisseur.
                reaction = agent_gratuit.reagir(None, str(exc))
                if mode_gratuit is not None and reaction.cooldown_minutes is not None:
                    with contextlib.suppress(Exception):
                        await agent_gratuit.signaler_echec(
                            db_tour, mode_gratuit.lane, reaction.cooldown_minutes
                        )
                if not terminaux:
                    terminaux.append(
                        {
                            "type": "error",
                            "payload": {
                                "message": "Erreur interne de l'agent. Le travail déjà fait est conservé."
                            },
                        }
                    )
            finally:
                # Instantané avant tout ``await`` : une boucle annulée peut
                # encore ajouter un message à sa prochaine reprise.
                horodater()
                # La conversation d'abord, puis le deroule qu'elle a pu lancer.
                ajouts = messages[depart:] + ajouts_guides
                heures = horodatages[depart:] + heures_guides
                if issue != "complet":
                    # Les écritures d'outils sont déjà en base : sans ce
                    # rattrapage, la source que l'agent vient de créer existe
                    # mais ne figure nulle part dans la conversation.
                    ajouts = _blocs_complets(ajouts)
                texte = _reponse_finale(deltas, ajouts)
                if reponse_verifiee and texte:
                    texte = reponse_verifiee[-1]
                if issue == "annule":
                    texte = _texte_interrompu(texte)
                    terminaux = [
                        {
                            "type": "error",
                            "payload": {
                                "message": "Tour arrêté. Le travail déjà fait est conservé."
                            },
                        }
                    ]
                usage = usage_capture[0] if usage_capture else None
                # Bouclier obligatoire : on arrive ici aussi par annulation, et
                # tout `await` non protégé relèverait aussitôt sans rien écrire.
                with anyio.CancelScope(shield=True):
                    try:
                        await _persister_tour(creator_id, session_id, ajouts, texte, usage, heures)
                    except Exception:  # noqa: BLE001  # la fin du tour doit partir quand meme
                        logger.exception("Persistance du tour impossible, session %s", session_id)
                    if mode_decouverte and issue == "complet":
                        with contextlib.suppress(Exception):
                            async with async_session_maker() as db_dedie:
                                await consommer_message(db_dedie, creator_id)
                for event in terminaux:
                    publier(event)

    agent_tours.lancer(tour, travail)

    async def gen():
        yield _sse({"type": "session", "payload": {"id": str(session_id)}})
        # Quitter ce générateur ne touche plus au tour : il continue sans le
        # client, qui le rattrape par `GET /agent/sessions/{id}/flux`.
        async for event in tour.suivre():
            yield _sse(event)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_ENTETES_SSE)


@router.get("/sessions/{session_id}/flux")
async def suivre_tour(
    session_id: UUID,
    depuis: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Reprend le flux d'un tour à partir de l'événement numéro `depuis`.

    Un téléphone mis en veille, un proxy qui coupe au bout de cinq minutes : le
    tour a continué, et le client redemande ce qu'il n'a pas reçu. 404 quand
    aucun tour n'est rejouable : la conversation en base fait alors foi.
    """
    tour = agent_tours.obtenir(session_id, current_user.id)
    if tour is None:
        raise _aucun_tour()

    async def gen():
        async for event in tour.suivre(depuis):
            yield _sse(event)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_ENTETES_SSE)


@router.post("/sessions/{session_id}/arreter", status_code=status.HTTP_204_NO_CONTENT)
async def arreter_tour(session_id: UUID, current_user: User = Depends(get_current_user)):
    """Arrête le tour en cours. Fermer la connexion ne l'arrête plus."""
    if not agent_tours.arreter(session_id, current_user.id):
        raise _aucun_tour()


def _conflit_tour() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "tour_en_cours",
            "message": "L'agent termine encore la réponse précédente. Elle s'affiche dès qu'elle est prête.",
        },
    )


def _aucun_tour() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "aucun_tour", "message": "Aucun tour en cours sur cette conversation."},
    )


def _reponse_finale(deltas: dict[int, list[str]], ajouts: list[dict[str, Any]]) -> str:
    """Le texte du dernier appel au modèle, et lui seul.

    Tous les morceaux du tour étaient recollés : le plan écrit avant d'agir,
    les phrases de transition entre deux outils, puis la conclusion. Le plan
    annonçait des extraits qui n'ont jamais été posés, et se lisait comme le
    bilan. Les textes intermédiaires sont déjà dans l'historique, portés par
    les messages qui appellent les outils.
    """
    if not deltas:
        return ""
    texte = "".join(deltas[max(deltas)])
    # Le dernier appel a pu demander des outils (tour coupé, pause) : son texte
    # est alors déjà écrit avec eux, le reprendre le doublerait.
    precedents = [m.get("content") or "" for m in ajouts if m.get("role") == "assistant"]
    if precedents and precedents[-1].strip() == texte.strip():
        return ""
    return texte


def _blocs_complets(ajouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coupe un tour interrompu à son dernier bloc complet.

    Un ``assistant`` porteur de ``tool_calls`` dont les réponses manquent
    laisserait des appels orphelins dans l'historique, et tous les
    fournisseurs rejettent le tour suivant. Mieux vaut perdre l'appel amorcé
    que rendre la session inutilisable.

    Seul le dernier bloc peut être incomplet : les précédents avaient reçu
    leurs réponses avant que l'assistant suivant ne soit ajouté. On compte les
    réponses plutôt que d'apparier les identifiants, parce que ``_executer_tour``
    en synthétise un quand le fournisseur n'en donne pas.
    """
    for i in range(len(ajouts) - 1, -1, -1):
        appels = ajouts[i].get("tool_calls")
        if ajouts[i].get("role") != "assistant" or not appels:
            continue
        repondus = sum(1 for m in ajouts[i + 1 :] if m.get("role") == "tool")
        return ajouts if repondus >= len(appels) else ajouts[:i]
    return ajouts


def _texte_interrompu(texte: str) -> str:
    """Marque une réponse coupée en cours de route.

    Sans la marque, le modèle relit au tour suivant une phrase tronquée comme
    s'il l'avait finie, et enchaîne sur une pensée qu'il n'a jamais eue.
    """
    if not texte:
        return ""
    return f"{texte}\n\n[Réponse interrompue : le tour a été arrêté avant la fin.]"


def heures_croissantes(heures: list[datetime], nombre: int) -> list[datetime]:
    """Une heure par message du tour, strictement croissante. Fonction pure.

    L'historique se relit trie par heure. Mesure du 2026-09-15 : le deroule
    donnait a tous les messages d'une etape l'heure de sa fin ; relus dans un
    ordre quelconque, appels et reponses d'outils se separaient, et Mistral
    refusait chaque message suivant de la conversation.
    """
    rendues: list[datetime] = []
    for rang in range(nombre):
        heure = heures[rang] if rang < len(heures) else datetime.now(UTC).replace(tzinfo=None)
        if rendues and heure <= rendues[-1]:
            heure = rendues[-1] + timedelta(microseconds=1)
        rendues.append(heure)
    return rendues


async def _persister_tour(
    creator_id: UUID,
    session_id: UUID,
    ajouts: list[dict[str, Any]],
    reponse_finale: str,
    usage: dict[str, Any] | None = None,
    heures: list[datetime] | None = None,
) -> None:
    """Ecrit le tour en base, append-only, dans l'ordre ou il s'est produit.

    `heures[i]` est l'heure a laquelle `ajouts[i]` est apparu pendant le tour.

    La reponse textuelle finale n'est pas dans ``messages`` : la boucle
    l'emet en ``message_delta`` sans la rajouter a l'historique. On la
    recompose ici pour que le tour suivant la voie.

    Ouvre sa propre session de base, independante de celle injectee par
    FastAPI : le tour est persiste apres la fin du flux SSE, quand la session
    du middleware peut deja etre fermee (client parti, timeout du serveur).
    """
    async with async_session_maker() as db:
        session = await agent_sessions.obtenir(db, creator_id, session_id)
        heures = heures_croissantes(heures or [], len(ajouts))
        for rang, message in enumerate(ajouts):
            heure = heures[rang]
            # Le prompt systeme est reconstruit en tete a chaque tour. Un message
            # systeme ecrit ici serait rejoue en second, et Gemini refuse un
            # historique qui en porte deux. La boucle en insere un quand elle
            # redemande une reponse (`controle_relance`) : c'est une consigne
            # valable pour ce tour, pas une trace de la conversation.
            if message.get("role") == "system":
                continue
            if message.get("role") == "tool":
                await agent_sessions.ajouter_message(
                    db,
                    session,
                    role="tool",
                    content=message.get("content") or "",
                    tool_name=message.get("name"),
                    tool_call_id=message.get("tool_call_id"),
                    created_at=heure,
                )
            else:
                await agent_sessions.ajouter_message(
                    db,
                    session,
                    role=message.get("role") or "assistant",
                    content=message.get("content") or "",
                    tool_calls=message.get("tool_calls"),
                    created_at=heure,
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
