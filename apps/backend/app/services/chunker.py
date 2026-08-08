"""Decoupe un texte en extraits proposables, sans reseau ni cle.

Mesure du 2026-08-08, sur dix URLs dont les quatre personas de l'audit :
**cinq ne rendent aucun texte exploitable** a `_html_scrape` -- NYT,
ScienceDirect, treasury.gov et Cell rendent zero caractere, YouTube 313. La
suggestion de citations, qui lit `page_text`, echoue donc une fois sur deux, et
sur ScienceDirect ou Cell une capture Wayback ne rattraperait rien : le texte
est derriere un paywall.

Le seul repli qui couvre tous les cas est le texte que la personne a sous les
yeux et colle elle-meme. Ce module en fait des extraits. Il ne depend d'aucun
service exterieur -- c'est precisement ce qui lui permet d'etre le plancher.

Il ne reecrit jamais le texte : un extrait sert a citer. Et il ne coupe qu'aux
frontieres de phrase ou de paragraphe, la taille demandee etant une cible et
non un couperet. Couper au milieu d'une phrase produirait un fragment, la meme
faute que le titre pris sur le texte d'un lien (#327).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Unite(str, Enum):
    """L'unite dans laquelle la taille cible est exprimee."""

    CARACTERES = "caracteres"
    MOTS = "mots"
    TOKENS = "tokens"


@dataclass(frozen=True)
class Chunk:
    """Un extrait candidat et sa place exacte dans le texte d'origine.

    `start`/`end` servent les bornes reglables de l'interface : deplacer une
    borne, c'est reindexer dans le meme texte, pas redecouper.
    """

    text: str
    start: int
    end: int


# Un token vaut ~4 caracteres sur du texte courant. L'approximation est
# assumee : mesurer exactement exigerait le tokenizer du modele, donc une
# dependance et un telechargement, pour un reglage que l'auteur·ice corrige a
# l'oeil de toute facon.
_CARACTERES_PAR_TOKEN = 4

# Fin de phrase : ponctuation forte, guillemets ou parenthese fermante
# eventuels, puis une espace. Le point d'une abreviation n'est pas suivi d'une
# majuscule apres espace dans la majorite des cas ; on accepte le faux positif
# residuel, qui coute une coupe un peu tot, jamais un texte deforme.
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?…])[\"'»)\]]*\s+")

_PARAGRAPHE = re.compile(r"\n\s*\n")

# Bornes de la taille suggeree, en caracteres. En deca on propose des bribes,
# au-dela l'extrait cesse d'etre une citation et devient une reproduction.
_CIBLE_MIN = 200
_CIBLE_MAX = 1000

# Au-dela, l'ecran devient illisible : mieux vaut des morceaux plus gros.
_MORCEAUX_VISES = 8


def compter(texte: str, unite: Unite) -> int:
    """Mesure `texte` dans l'unite demandee."""
    if unite is Unite.CARACTERES:
        return len(texte)
    if unite is Unite.MOTS:
        return len(texte.split())
    return max(1, round(len(texte) / _CARACTERES_PAR_TOKEN)) if texte else 0


def _en_caracteres(taille: int, unite: Unite) -> int:
    """Ramene une cible a des caracteres : le decoupage n'y travaille qu'ainsi."""
    if unite is Unite.CARACTERES:
        return taille
    if unite is Unite.MOTS:
        return taille * 6  # ~5 lettres et une espace
    return taille * _CARACTERES_PAR_TOKEN


def suggerer_taille(texte: str, unite: Unite) -> int:
    """La cible que « un bouton » propose, a corriger ensuite a la main.

    Elle vise un nombre de morceaux lisible a l'ecran plutot qu'une longueur
    absolue : un texte de trois phrases et un chapitre entier n'appellent pas
    le meme grain.
    """
    brut = len(texte.strip()) / _MORCEAUX_VISES if texte.strip() else _CIBLE_MIN
    cible = min(_CIBLE_MAX, max(_CIBLE_MIN, round(brut)))
    if unite is Unite.CARACTERES:
        return cible
    if unite is Unite.MOTS:
        return max(1, cible // 6)
    return max(1, cible // _CARACTERES_PAR_TOKEN)


def _phrases(bloc: str, decalage: int) -> list[tuple[int, int]]:
    """Les frontieres (debut, fin) des phrases de `bloc`, en index absolus."""
    bornes: list[tuple[int, int]] = []
    curseur = 0
    for coupe in _FIN_DE_PHRASE.finditer(bloc):
        bornes.append((decalage + curseur, decalage + coupe.start()))
        curseur = coupe.end()
    if curseur < len(bloc):
        bornes.append((decalage + curseur, decalage + len(bloc)))
    return [(d, f) for d, f in bornes if bloc[d - decalage : f - decalage].strip()]


def _blocs(texte: str) -> list[tuple[int, int]]:
    """Les paragraphes, en index absolus. Un saut est toujours une coupe."""
    bornes: list[tuple[int, int]] = []
    curseur = 0
    for coupe in _PARAGRAPHE.finditer(texte):
        bornes.append((curseur, coupe.start()))
        curseur = coupe.end()
    bornes.append((curseur, len(texte)))
    return [(d, f) for d, f in bornes if texte[d:f].strip()]


def chunk_text(texte: str, taille: int, unite: Unite = Unite.CARACTERES) -> list[Chunk]:
    """Decoupe `texte` en extraits d'environ `taille` unites.

    On accumule des phrases entieres jusqu'a depasser la cible, sans jamais
    couper a l'interieur de l'une d'elles : une phrase plus longue que la cible
    fait donc un morceau plus long, ce qui vaut mieux qu'un fragment.
    """
    if not texte.strip() or taille <= 0:
        return []

    cible = max(1, _en_caracteres(taille, unite))
    morceaux: list[Chunk] = []

    for bloc_debut, bloc_fin in _blocs(texte):
        debut: int | None = None
        fin = bloc_debut
        for phrase_debut, phrase_fin in _phrases(texte[bloc_debut:bloc_fin], bloc_debut):
            if debut is None:
                debut = phrase_debut
            fin = phrase_fin
            if fin - debut >= cible:
                morceaux.append(Chunk(texte[debut:fin].strip(), debut, fin))
                debut = None
        if debut is not None:
            morceaux.append(Chunk(texte[debut:fin].strip(), debut, fin))

    return [m for m in morceaux if m.text]
