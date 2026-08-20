"""Approbations humaines en attente, le temps d'un flux SSE.

Quand la boucle rencontre une action sensible, elle émet ``approval_request``
et **s'arrête sur un ``Future``**. L'utilisateur répond dans l'UI, le endpoint
``POST /agent/approve`` résout le ``Future``, et la boucle reprend là où elle
en était.

L'attente vit en mémoire du processus, pas en base : elle ne survit
volontairement pas à un redémarrage. Une demande d'approbation orpheline dont
personne ne se souvient pourquoi elle existe est pire qu'un refus, et le flux
SSE qui l'attendait est de toute façon mort avec le processus. Le moteur
tourne in-process sur un worker unique (contrainte e2-micro, cf. plan), donc
un dict de module suffit.

Le ``creator_id`` est stocké avec chaque attente : sans lui, connaître un
``request_id`` suffirait à approuver la publication d'un autre créateur.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

#: Au-delà, on refuse. Un onglet fermé ne doit pas laisser un `Future`
#: immortel retenir une tâche et une session de base.
DELAI_MAX = 300.0

_EN_ATTENTE: dict[str, tuple[UUID, asyncio.Future[bool]]] = {}


class ApprovalInconnueError(LookupError):
    """Aucune demande en attente sous cet identifiant, pour ce créateur."""


def enregistrer(request_id: str, creator_id: UUID) -> asyncio.Future[bool]:
    future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    _EN_ATTENTE[request_id] = (creator_id, future)
    return future


def oublier(request_id: str) -> None:
    _EN_ATTENTE.pop(request_id, None)


def resoudre(request_id: str, creator_id: UUID, approuve: bool) -> None:
    """Répond à une demande en attente. Lève si elle n'existe pas ou n'est pas à ce créateur."""
    entree = _EN_ATTENTE.get(request_id)
    if entree is None or entree[0] != creator_id:
        # Même message dans les deux cas : distinguer « inexistante » de
        # « pas la tienne » dirait à un tiers qu'une demande existe.
        raise ApprovalInconnueError("Aucune demande d'approbation en attente sous cet identifiant.")
    _, future = entree
    if not future.done():
        future.set_result(approuve)
    _EN_ATTENTE.pop(request_id, None)


async def attendre(request_id: str, creator_id: UUID, *, delai: float = DELAI_MAX) -> bool:
    """Suspend jusqu'à la réponse humaine. Rend ``False`` au-delà du délai."""
    future = enregistrer(request_id, creator_id)
    try:
        return await asyncio.wait_for(future, timeout=delai)
    except TimeoutError:
        logger.info("Approbation %s expirée après %.0fs, refusée", request_id, delai)
        return False
    finally:
        oublier(request_id)
