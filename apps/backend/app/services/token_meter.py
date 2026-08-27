"""Mesure du contexte envoyé au fournisseur, en tokens.

Un budget de compaction ne vaut que ce que vaut la mesure qui le déclenche.
Compter les caractères et diviser se trompe dans les deux sens : le français
accentué tokenise plus dense que l'anglais, et l'encadrement JSON gonfle les
messages courts. Se tromper vers le bas est le cas coûteux, c'est celui où le
fournisseur refuse et où la session tombe au budget de repli.

Le fournisseur, lui, renvoie ``prompt_tokens`` à chaque réponse : le compte
exact, avec son propre tokeniseur, de ce qu'il vient de lire. C'est une vérité
gratuite qu'on jetait. On s'y ancre, et on n'estime plus que ce qui a été
ajouté depuis.

Pas de ``tiktoken`` ici, à rebours du plan d'intégration : c'est le tokeniseur
d'OpenAI, et Philum route vers Gemini, Mistral, Anthropic et Z.ai, dont les
tokeniseurs s'écartent de 10 à 20 % sur du français. Il coûterait une
dépendance et un téléchargement au premier appel pour une précision fausse là
où l'ancre, elle, est juste par construction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: Caractères par token. Les tokeniseurs BPE tournent autour de 4 sur de
#: l'anglais et de 3 sur du français accentué. On vise le bas de la fourchette :
#: surestimer fait compacter un peu tôt, sous-estimer fait refuser le
#: fournisseur et tomber au budget de repli, ce qui coûte la conversation.
CARACTERES_PAR_TOKEN = 3.2

#: Marge par message : l'encadrement de rôle que le protocole ajoute autour de
#: chaque entrée, invisible dans le JSON qu'on sérialise.
MARGE_PAR_MESSAGE = 8

#: Plafond du facteur de recalage. Un écart mesuré au-delà ne vient plus du
#: tokeniseur mais d'un décompte qu'on interprète mal ; le suivre
#: aveuglément ferait compacter une session qui tient largement.
FACTEUR_MAX = 3.0


def estimer_message(message: dict[str, Any]) -> int:
    """Coût approximatif d'un message, en tokens.

    On sérialise le message entier plutôt que son seul ``content`` : les
    arguments d'appels d'outils, souvent les plus longs, ne compteraient pour
    rien.
    """
    try:
        brut = json.dumps(message, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        brut = str(message)
    return int(len(brut) / CARACTERES_PAR_TOKEN) + MARGE_PAR_MESSAGE


def estimer(messages: list[dict[str, Any]]) -> int:
    """Coût approximatif d'une liste de messages, en tokens."""
    return sum(estimer_message(m) for m in messages)


@dataclass(frozen=True)
class Ancre:
    """Un ``prompt_tokens`` du fournisseur, et le préfixe qu'il couvrait."""

    #: Nombre de messages que le fournisseur avait sous les yeux.
    messages: int
    #: Ce qu'il a compté, tokeniseur maison. Inclut le schéma des outils, qui
    #: n'est pas dans les messages mais part à chaque appel : l'attribuer au
    #: préfixe le surestime d'une constante toujours réellement payée.
    tokens: int
    #: Ce que l'estimation par caractères donnait du même préfixe, pour
    #: mesurer l'écart.
    estimation: int


class TokenMeter:
    """Mesure une liste de messages, ancrée sur le dernier compte du fournisseur.

    Sans ancre, se comporte exactement comme :func:`estimer`. Avec une ancre
    valide, rend le compte réel du préfixe plus l'estimation recalée du reste.

    L'ancre ne vaut que pour un préfixe : dès que la liste est recoupée par la
    compaction, elle ne décrit plus rien et doit être oubliée.
    """

    __slots__ = ("_ancre",)

    def __init__(self) -> None:
        self._ancre: Ancre | None = None

    @property
    def ancre(self) -> Ancre | None:
        return self._ancre

    def ancrer(self, messages_envoyes: list[dict[str, Any]], prompt_tokens: int) -> None:
        """Enregistre le compte réel d'un envoi. Ignore un compte non exploitable."""
        if prompt_tokens <= 0 or not messages_envoyes:
            return
        self._ancre = Ancre(
            messages=len(messages_envoyes),
            tokens=prompt_tokens,
            estimation=max(1, estimer(messages_envoyes)),
        )

    def oublier(self) -> None:
        """Invalide l'ancre. À appeler dès que la liste cesse d'être un ajout."""
        self._ancre = None

    @property
    def facteur(self) -> float:
        """De combien l'estimation sous-compte, d'après la dernière ancre.

        Borné à 1.0 par le bas : l'estimation est déjà volontairement haute,
        la corriger vers le bas rendrait le budget optimiste, ce qui est
        précisément le défaut qu'on répare.
        """
        if self._ancre is None:
            return 1.0
        return min(max(self._ancre.tokens / self._ancre.estimation, 1.0), FACTEUR_MAX)

    def mesurer(self, messages: list[dict[str, Any]]) -> int:
        """Taille de ``messages`` en tokens, la meilleure connue."""
        ancre = self._ancre
        if ancre is None:
            return estimer(messages)
        if ancre.messages > len(messages):
            # La liste a été recoupée sous l'ancre : le préfixe mesuré n'existe
            # plus. Le facteur, lui, reste une propriété du tokeniseur.
            return int(estimer(messages) * self.facteur)
        return ancre.tokens + int(estimer(messages[ancre.messages :]) * self.facteur)
