"""Retrouver un extrait cite dans une source qui a bouge.

Un extrait qui ne porte que son texte se retrouve par recherche exacte, et
cesse d'etre retrouvable des que la page corrige une coquille ou change de
gabarit. L'extrait devient alors indiscernable d'une citation inventee — le
mode d'echec meme que Philum existe pour eliminer.

L'architecture est celle d'Hypothes.is, dont la specification est publique :
on stocke *plusieurs* selecteurs pour la meme cible et on les essaie du moins
cher au plus robuste.

  1. **Citation** — le texte exact, aux espaces pres. Robuste au deplacement,
     mais muet si un seul mot a change. Le voisinage (`prefix`/`suffix`)
     departage les occurrences multiples, et l'offset d'origine les ex aequo.
  2. **Approche** — plus proche voisin. Seul recours quand le texte lui-meme a
     change ; il rend `exact=False`, car l'appelant doit pouvoir dire a la
     personne que la source ne porte plus tout a fait ces mots.

L'offset n'est pas une strategie a lui seul : une page qui gagne un paragraphe
le rend faux sans rien signaler, et une position fausse designe du texte reel,
donc plausible. Il reste stocke comme indice de departage, jamais comme adresse.

Le seuil du dernier etage est le point delicat. Un ancrage complaisant est
*pire* que pas d'ancrage : il affirmerait que la source contient un passage
qu'elle ne contient pas. En cas de doute, on ne rend rien.

Aucune dependance : `difflib` est dans la bibliotheque standard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

# Assez de voisinage pour departager deux occurrences d'une meme phrase, assez
# peu pour ne pas recopier la page dans la base.
CONTEXTE = 48

# Part des caracteres qui doivent correspondre pour qu'on ose dire « c'est ce
# passage ». En dessous, on prefere l'aveu d'echec a une affirmation fausse.
SEUIL = 0.75


@dataclass(frozen=True)
class Selecteurs:
    """Ce qu'on stocke d'un extrait pour pouvoir le retrouver plus tard."""

    quote: str
    prefix: str
    suffix: str
    offset: int | None


@dataclass(frozen=True)
class Ancrage:
    """Ou l'extrait a ete retrouve, et a quel point on en est sur."""

    start: int
    end: int
    texte: str
    #: Faux quand seule l'approche a repondu : la source ne porte plus
    #: exactement ces mots, et l'interface doit pouvoir le dire.
    exact: bool


def selecteurs_pour(page_text: str, start: int, end: int) -> Selecteurs:
    """Capture le passage `[start, end)` et de quoi le reconnaitre ailleurs."""
    return Selecteurs(
        quote=page_text[start:end],
        prefix=page_text[max(0, start - CONTEXTE) : start],
        suffix=page_text[end : end + CONTEXTE],
        offset=start,
    )


def _normalise(texte: str) -> tuple[str, list[int]]:
    """Texte aux espaces reduits, plus l'index d'origine de chaque caractere.

    La table de correspondance est ce qui permet de chercher sur une forme
    normalisee tout en rendant des offsets utilisables dans le texte reel :
    sans elle, un ancrage designerait une position dans un texte qui n'existe
    nulle part.
    """
    sortie: list[str] = []
    index: list[int] = []
    espace_en_cours = False
    for i, c in enumerate(texte):
        if c.isspace():
            if sortie and not espace_en_cours:
                sortie.append(" ")
                index.append(i)
            espace_en_cours = True
            continue
        espace_en_cours = False
        sortie.append(c)
        index.append(i)
    # Sentinelle : borne de fin d'un passage qui finit le texte.
    index.append(len(texte))
    return "".join(sortie).rstrip(), index


def _fin_reelle(page: str, index: list[int], fin_norm: int) -> int:
    """Borne de fin dans le texte d'origine, espaces de queue exclus."""
    brut = index[min(fin_norm, len(index) - 1)]
    return len(page[:brut].rstrip())


def _par_citation(
    page: str, page_norm: str, index: list[int], sel: Selecteurs
) -> tuple[int, int] | None:
    """Occurrence exacte du texte, celle dont le voisinage colle le mieux."""
    quote_norm, _ = _normalise(sel.quote)
    if not quote_norm:
        return None
    occurrences = [m.start() for m in re.finditer(re.escape(quote_norm), page_norm)]
    if not occurrences:
        return None

    prefix_norm, _ = _normalise(sel.prefix)
    suffix_norm, _ = _normalise(sel.suffix)

    def voisinage(debut: int) -> tuple[float, int]:
        fin = debut + len(quote_norm)
        avant = page_norm[max(0, debut - CONTEXTE * 2) : debut]
        apres = page_norm[fin : fin + CONTEXTE * 2]
        score = 0.0
        if prefix_norm:
            score += SequenceMatcher(None, avant[-len(prefix_norm) :], prefix_norm).ratio()
        if suffix_norm:
            score += SequenceMatcher(None, apres[: len(suffix_norm)], suffix_norm).ratio()
        # A voisinage egal — deux passages identiques dans un contexte lui aussi
        # identique — la position d'origine tranche. C'est tout ce que l'offset
        # sert encore a faire une fois la page modifiee : un indice, pas une
        # adresse.
        proximite = -abs(debut - sel.offset) if sel.offset is not None else 0
        return score, proximite

    debut = max(occurrences, key=voisinage) if len(occurrences) > 1 else occurrences[0]
    return index[debut], _fin_reelle(page, index, debut + len(quote_norm))


def _par_approche(
    page: str, page_norm: str, index: list[int], sel: Selecteurs
) -> tuple[int, int] | None:
    """Plus proche voisin, si la ressemblance depasse le seuil."""
    quote_norm, _ = _normalise(sel.quote)
    if not quote_norm or not page_norm:
        return None

    sm = SequenceMatcher(None, page_norm, quote_norm, autojunk=False)
    blocs = [b for b in sm.get_matching_blocks() if b.size > 0]
    if not blocs:
        return None

    # Les blocs communs bornent la fenetre : on remonte du premier au dernier,
    # en reportant de part et d'autre ce qui manque de la citation.
    debut = max(0, blocs[0].a - blocs[0].b)
    dernier = blocs[-1]
    fin = min(
        len(page_norm), dernier.a + dernier.size + (len(quote_norm) - dernier.b - dernier.size)
    )
    if fin <= debut:
        return None

    if SequenceMatcher(None, page_norm[debut:fin], quote_norm).ratio() < SEUIL:
        return None
    return index[debut], _fin_reelle(page, index, fin)


def ancrer(page_text: str, sel: Selecteurs) -> Ancrage | None:
    """Retrouve l'extrait dans `page_text`, ou rend `None` faute de certitude."""
    if not page_text.strip() or not sel.quote.strip():
        return None

    page_norm, index = _normalise(page_text)

    for strategie, exact in ((_par_citation, True), (_par_approche, False)):
        bornes = strategie(page_text, page_norm, index, sel)
        if bornes is None:
            continue
        debut, fin = bornes
        return Ancrage(start=debut, end=fin, texte=page_text[debut:fin], exact=exact)
    return None
