"""Scoring syntaxique universel — dernier filet anti-artefacts.

Ne juge PAS le type de source (livre, tweet, reportage, article
scientifique) mais UNIQUEMENT la coherence syntaxique du titre : le
signal est agnostique aux domaines.

Utilise en dernier ressort apres section-detection et dedup. Attrape
principalement les residus de parsing (GROBID/LLM) qui auraient survecu
aux etages precedents : fragments de citation, titres tronques, ou
titres avec sequences de mots dupliquees (artefacts S2).

Pas de penalite pour :
- year absente (un reportage peut ne pas avoir de date)
- titre court (livres : '1984', 'Dune', 'Sapiens')
- pas de DOI/ISBN/ArXiv (blog, tweet, video n'ont pas d'external ID)
- pas de journal (par nature absent hors scholarly)
"""

from __future__ import annotations

import re

from app.services.import_parsers import ImportedRef

# Fragment complet de citation : le titre TOUT ENTIER ressemble a une
# reference numerique/pagination ("12", "[12]", "[12] p. 45", "p. 45-67").
_CITATION_FRAGMENT_RE = re.compile(
    r"^\s*\[?\d+\]?[\s.,]*(?:p{1,2}\.|pp\.)?\s*\d*[\-\d,\s]*$",
    re.IGNORECASE,
)

# Ponctuation ouvrante non fermee en fin de titre (troncature evidente,
# cross-langue). '-' final aussi (« Development of- »).
_OPEN_TAIL_RE = re.compile(r'[«("\[{\-]\s*$')


def _has_duplicate_run(title: str) -> bool:
    """Sequence de >=2 mots consecutifs identiques :
    "Neural Circuits Neural Circuits". n=2 minimum pour catcher les
    concatenations S2 qui doublent une paire courte.
    """
    words = [w.lower().strip(".,;:") for w in title.split() if w]
    for n in range(2, min(6, len(words) // 2 + 1)):
        for i in range(len(words) - 2 * n + 1):
            if words[i : i + n] == words[i + n : i + 2 * n]:
                return True
    return False


def syntactic_score(ref: ImportedRef) -> float:
    """Retourne un score de coherence syntaxique 0.0-1.0.

    1.0 = parfaitement coherent. < 0.4 = fortement suspect de parsing rate.
    """
    title = (ref.title or "").strip()
    url = (ref.url or "").strip()

    # Titre vide ET url vide = drop dur
    if not title and not url:
        return 0.0

    if not title:
        # Pas de titre mais une URL : ref potentiellement valide (blog, tweet)
        return 0.7

    score = 1.0

    # 1. Fragment de citation complet ("12", "[12] p. 45", "p. 45-67") :
    # signal tres fort d'un parsing rate. Un titre legitime meme court
    # ("Dune", "Sapiens") ne matche PAS ce pattern.
    if _CITATION_FRAGMENT_RE.match(title):
        score -= 0.7

    # 2. Ponctuation ouvrante non fermee en fin
    if _OPEN_TAIL_RE.search(title):
        score -= 0.7

    # 3. Sequence de mots dupliques
    if _has_duplicate_run(title):
        score -= 0.7

    return max(0.0, score)


def should_drop(ref: ImportedRef, threshold: float = 0.4) -> bool:
    """True si la ref doit etre droppee (score sous seuil)."""
    return syntactic_score(ref) < threshold
