"""Fusion de plusieurs recherches par le rang reciproque.

Philum cherche les extraits de deux facons qui ne se voient pas : par le sens,
au cosinus sur les vecteurs, et par les mots, au `ILIKE` sur le texte. Un
extrait qui porte exactement le mot cherche mais dont le sens est loin sort de
l'une et pas de l'autre, et reciproquement.

Les fusionner par leurs scores serait une faute : une similarite cosinus et un
nombre d'occurrences ne vivent pas sur la meme echelle, et les ramener l'une a
l'autre demanderait une calibration a refaire a chaque changement de modele
d'embeddings. Le rang reciproque ne compare que des rangs, qui sont
commensurables par construction.

Le module ne connait ni extrait ni vecteur : il prend des listes ordonnees
d'identifiants et rend un ordre. C'est ce qui le rend testable seul.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

#: Constante du rang reciproque, reprise telle quelle de la litterature.
#:
#: Elle amortit l'ecart entre les premieres places : passer du rang 1 au rang 2
#: coute peu, ce qui evite qu'une seule jambe tres sure impose son ordre. Aucune
#: calibration sur notre corpus ne la justifie, et aucune n'est necessaire :
#: c'est precisement l'interet de la methode, qui ne compare jamais deux scores
#: issus d'echelles differentes.
K_RANG = 60


@dataclass(frozen=True)
class Fusionne[T]:
    """Un identifiant, son score fusionne, et les jambes qui l'ont trouve.

    Les jambes voyagent avec le resultat parce qu'une fusion muette est une
    boite noire : sans elles, personne ne peut dire si un extrait remonte parce
    qu'il porte le mot cherche ou parce qu'il en porte le sens.
    """

    identifiant: T
    score: float
    jambes: frozenset[str]


def fusionner[T](classements: Mapping[str, Sequence[T]]) -> list[Fusionne[T]]:
    """Fusionne des listes ordonnees, de la meilleure correspondance a la pire.

    Chaque jambe est une liste d'identifiants deja triee par sa propre mesure.
    Le score d'un identifiant est la somme des ``1 / (K_RANG + rang)`` sur les
    jambes ou il figure, en comptant les rangs a partir de 1.

    Une jambe vide n'apporte rien et ne retire rien : elle ne contribue a aucun
    score, donc l'ordre des autres tient. C'est le comportement voulu quand la
    recherche par le sens est indisponible.

    A egalite de score, l'ordre suit celui de la premiere jambe qui a trouve
    l'identifiant, ce qui rend le resultat stable d'un appel a l'autre.
    """
    scores: dict[T, float] = {}
    jambes: dict[T, set[str]] = {}
    arrivee: dict[T, int] = {}
    for nom, classement in classements.items():
        for rang, identifiant in enumerate(classement, start=1):
            scores[identifiant] = scores.get(identifiant, 0.0) + 1.0 / (K_RANG + rang)
            jambes.setdefault(identifiant, set()).add(nom)
            arrivee.setdefault(identifiant, len(arrivee))
    return [
        Fusionne(identifiant, scores[identifiant], frozenset(jambes[identifiant]))
        for identifiant in sorted(scores, key=lambda i: (-scores[i], arrivee[i]))
    ]
