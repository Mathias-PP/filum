"""Que faire quand un fournisseur refuse : reessayer, replier, ou renoncer.

Philum gere deja le 429 avec son `retryDelay`, le repli du streaming vers le
mode bloquant sur 400, et un backoff court sur les 5xx. Ce qui manquait tient en
une distinction : un createur qui a configure trois cles n'en voyait essayer
qu'une, et rien ne separait l'echec qu'une autre cle guerirait de celui qu'elle
reproduirait a l'identique.

C'est cette derniere categorie qui compte. Une cle revoquee, un modele inconnu,
un refus de filtrage de contenu : basculer sur la cle suivante ne change rien au
resultat, fait payer trois appels au lieu d'un, et compte un incident contre des
cles saines. Le verdict `ABANDONNER` existe pour cela.

Chaque decision porte sa raison, en francais et destinee a etre lue : un repli
silencieux serait indistinguable d'une panne.

Repris de `OmniRoute` (audit `agent/audit/10-externes/`) : la classification
fermee des erreurs amont, le plafond sur le temps de repos, et la raison portee
par la decision. Pas son `accountFallback.ts`, 2405 lignes de scoring
multifactoriel pour choisir un compte parmi des milliers : Philum a trois
fournisseurs et un createur par session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Verdict(StrEnum):
    """Ce qu'il reste a tenter apres un refus."""

    #: La meme cle, plus tard. L'echec est transitoire et ne vient pas d'elle.
    REESSAYER = "reessayer"
    #: Une autre cle, maintenant. Celle-ci est saine mais indisponible.
    REPLIER = "replier"
    #: Rien. Toute autre cle reproduirait le meme echec, ou celui-ci est propre
    #: a la demande plutot qu'au fournisseur.
    ABANDONNER = "abandonner"


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    raison: str


#: Motifs de refus qui tiennent a la demande, pas au fournisseur. Cherches dans
#: le message quel que soit le statut HTTP : les fournisseurs ne s'accordent pas
#: sur le code a rendre pour un contenu refuse, et rendent 400, 403 ou 200 selon
#: les maisons.
_MOTIFS_DEMANDE = (
    "content filter",
    "content_filter",
    "safety",
    "blocked by",
    "prohibited_content",
    "recitation",
)

#: Motifs de quota. Un solde epuise se rend en 402, en 429, ou en 400 selon les
#: fournisseurs, d'ou la lecture du message en plus du statut.
_MOTIFS_QUOTA = (
    "quota",
    "insufficient",
    "balance",
    "credit",
    "billing",
    "rate limit",
)


def classer(statut: int | None, message: str = "") -> Decision:
    """Le verdict pour un refus amont, et pourquoi.

    `statut` a `None` designe un echec reseau : rien n'a ete refuse, la demande
    n'est pas arrivee. C'est le cas le plus clairement reessayable.
    """
    texte = message.lower()

    if any(motif in texte for motif in _MOTIFS_DEMANDE):
        return Decision(
            Verdict.ABANDONNER,
            "Le fournisseur a refuse le contenu de la demande. Une autre clé la refuserait aussi.",
        )

    if statut is None:
        return Decision(
            Verdict.REESSAYER,
            "Le fournisseur est injoignable. La demande n'est pas arrivée jusqu'à lui.",
        )

    if statut in (401, 403):
        return Decision(
            Verdict.ABANDONNER,
            "La clé est refusée : révoquée, expirée, ou sans droit sur ce modèle.",
        )

    if statut == 429 or (statut == 402) or any(motif in texte for motif in _MOTIFS_QUOTA):
        return Decision(
            Verdict.REPLIER,
            "Quota ou limite de débit atteinte sur cette clé. Une autre clé peut répondre.",
        )

    if statut in (400, 404, 422):
        return Decision(
            Verdict.ABANDONNER,
            "La demande est refusée en elle-même : modèle inconnu ou requête malformée.",
        )

    if statut >= 500:
        return Decision(
            Verdict.REESSAYER,
            "Panne côté fournisseur. L'incident ne vient pas de la clé.",
        )

    return Decision(
        Verdict.REPLIER,
        f"Réponse inattendue du fournisseur (HTTP {statut}). Une autre clé peut répondre.",
    )


#: Temps de repos apres un premier incident, puis double a chaque suivant.
_REPOS_INITIAL_S = 30.0

#: Plafond du temps de repos. Sans lui, une panne de dix minutes mettrait une clé
#: au repos pour des heures : le doublement est fait pour espacer les tentatives,
#: pas pour condamner une clé que le fournisseur a peut-être déjà rétablie.
_REPOS_MAX_S = 900.0


class Repos:
    """L'état de santé transitoire des clés, tenu en mémoire de processus.

    En mémoire et non en base : Philum tourne sur un conteneur unique, et
    persister un état qui se périme en quinze minutes coûterait une migration
    pour rien. Un passage en multi-instance devrait le déplacer, faute de quoi
    chaque instance apprendrait la panne de son côté.
    """

    def __init__(self) -> None:
        self._jusqu_a: dict[UUID, float] = {}
        self._incidents: dict[UUID, int] = {}

    def signaler(self, provider_id: UUID) -> float:
        """Met la clé au repos et rend la durée appliquée, en secondes."""
        incidents = self._incidents.get(provider_id, 0) + 1
        self._incidents[provider_id] = incidents
        duree = float(min(_REPOS_INITIAL_S * 2 ** (incidents - 1), _REPOS_MAX_S))
        self._jusqu_a[provider_id] = time.monotonic() + duree
        return duree

    def au_repos(self, provider_id: UUID) -> bool:
        fin = self._jusqu_a.get(provider_id)
        return fin is not None and time.monotonic() < fin

    def reussite(self, provider_id: UUID) -> None:
        """La clé a répondu : son historique d'incidents s'efface.

        Sans cet oubli, une clé qui tombe une fois par jour finirait au repos
        quinze minutes dès son premier incident du mois suivant.
        """
        self._jusqu_a.pop(provider_id, None)
        self._incidents.pop(provider_id, None)


#: Partagé par la boucle de chat. Une instance par processus, pas par session :
#: une clé épuisée l'est pour toutes les conversations en cours.
repos = Repos()
