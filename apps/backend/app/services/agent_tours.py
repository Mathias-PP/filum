"""Tours de l'agent detaches de la connexion qui les a lances.

Un tour tournait dans le flux SSE : quand la connexion tombait (telephone mis
en veille, verrouillage automatique, proxy Vercel coupe a 300 secondes), le
serveur annulait le tour. L'agent s'arretait au milieu d'une fiche, et la
conversation gardait « [Réponse interrompue] ».

Ici le tour vit dans une tache a part. Chaque evenement recoit un numero
(`seq`) et reste en memoire : un client qui revient demande la suite a partir
du dernier numero recu, et retrouve le tour la ou il l'avait laisse.

En memoire, donc propre au processus : le serveur tourne sur un seul worker,
comme l'exigent deja les approbations (`agent_approvals`). Un redemarrage perd
le registre, pas le tour deja persiste.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

#: Duree pendant laquelle un tour termine reste rejouable. Assez pour qu'un
#: client coupe juste avant la fin recoive ses derniers evenements plutot que de
#: relire la base ; au-dela, la conversation persistee fait foi.
CONSERVATION_APRES_FIN = 120.0

Publier = Callable[[dict[str, Any]], None]


class TourEnCoursError(RuntimeError):
    """Un tour tourne deja sur cette session."""


@dataclass
class Tour:
    session_id: UUID
    creator_id: UUID
    evenements: list[dict[str, Any]] = field(default_factory=list)
    termine: bool = False
    tache: asyncio.Task[None] | None = None
    _nouveau: asyncio.Event = field(default_factory=asyncio.Event)

    def publier(self, event: dict[str, Any]) -> None:
        self.evenements.append({**event, "seq": len(self.evenements)})
        self._reveiller()

    def clore(self) -> None:
        self.termine = True
        self._reveiller()

    def _reveiller(self) -> None:
        # Un evenement neuf par publication : ceux qui attendaient l'ancien sont
        # reveilles, les suivants attendront le prochain.
        ancien, self._nouveau = self._nouveau, asyncio.Event()
        ancien.set()

    async def suivre(self, depuis: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Rend les evenements a partir de `depuis`, puis la suite en direct."""
        i = max(depuis, 0)
        while True:
            signal = self._nouveau
            while i < len(self.evenements):
                yield self.evenements[i]
                i += 1
            if self.termine:
                return
            await signal.wait()


_TOURS: dict[UUID, Tour] = {}


def obtenir(session_id: UUID, creator_id: UUID) -> Tour | None:
    tour = _TOURS.get(session_id)
    # Meme reponse pour « aucun tour » et « tour d'un autre » : distinguer les
    # deux dirait a un tiers qu'une session existe.
    if tour is None or tour.creator_id != creator_id:
        return None
    return tour


def en_cours(session_id: UUID) -> bool:
    tour = _TOURS.get(session_id)
    return tour is not None and not tour.termine


def reserver(session_id: UUID, creator_id: UUID) -> Tour:
    """Pose le tour dans le registre, ou leve si un autre tourne deja.

    Synchrone de bout en bout : aucun `await` entre la verification et
    l'insertion, donc deux envois simultanes ne passent pas tous les deux.
    """
    if en_cours(session_id):
        raise TourEnCoursError("Un tour est deja en cours sur cette session.")
    tour = Tour(session_id=session_id, creator_id=creator_id)
    _TOURS[session_id] = tour
    return tour


def liberer(tour: Tour) -> None:
    """Retire un tour reserve qui ne demarrera pas (echec avant son lancement)."""
    tour.clore()
    _oublier(tour)


def lancer(tour: Tour, travail: Callable[[Publier], Awaitable[None]]) -> None:
    """Execute `travail` dans une tache qui survit a la requete."""

    async def executer() -> None:
        try:
            await travail(tour.publier)
        finally:
            tour.clore()
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_later(CONSERVATION_APRES_FIN, _oublier, tour)

    tour.tache = asyncio.create_task(executer())


def arreter(session_id: UUID, creator_id: UUID) -> bool:
    """Annule le tour en cours. Rend `False` s'il n'y en a pas."""
    tour = obtenir(session_id, creator_id)
    if tour is None or tour.termine or tour.tache is None:
        return False
    tour.tache.cancel()
    return True


def _oublier(tour: Tour) -> None:
    # Un tour plus recent a pu prendre la place : ne retirer que celui-ci.
    if _TOURS.get(tour.session_id) is tour:
        del _TOURS[tour.session_id]
