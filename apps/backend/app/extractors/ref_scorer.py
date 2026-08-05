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

from app.services.import_parsers import ImportedRef, _doi_from_url

# Fragment complet de citation : le titre TOUT ENTIER ressemble a une
# reference numerique/pagination ("12", "[12]", "[12] p. 45", "p. 45-67").
_CITATION_FRAGMENT_RE = re.compile(
    r"^\s*\[?\d+\]?[\s.,]*(?:p{1,2}\.|pp\.)?\s*\d*[\-\d,\s]*$",
    re.IGNORECASE,
)

# Ponctuation ouvrante non fermee en fin de titre (troncature evidente,
# cross-langue). '-' final aussi (« Development of- »).
_OPEN_TAIL_RE = re.compile(r'[«("\[{\-]\s*$')


# Part du titre que la repetition doit couvrir pour compter comme artefact.
#
# Une concatenation ratee duplique le titre, ou peu s'en faut ("Neural Circuits
# Neural Circuits"). Une repetition qui ne couvre qu'une fraction du texte est,
# elle, ordinaire : listes d'auteurs homonymes ("Nasr I, Nasr I, ..."), titres
# qui reprennent une expression ("... risk of celiac disease: risk of celiac
# disease and age at gluten introduction ..."). Sans ce seuil, trois references
# reelles de la revue BMC 10.1186/s12916-019-1380-z disparaissaient sans trace.
_DUPLICATE_RUN_MIN_SHARE = 0.5


def _duplicate_run_share(title: str) -> float:
    """Part des mots du titre couverte par la plus longue sequence repetee
    immediatement apres elle-meme. 0.0 si aucune.
    """
    words = [w.lower().strip(".,;:") for w in title.split() if w]
    if not words:
        return 0.0
    longest = 0
    for n in range(2, min(6, len(words) // 2 + 1)):
        for i in range(len(words) - 2 * n + 1):
            if words[i : i + n] == words[i + n : i + 2 * n]:
                longest = max(longest, 2 * n)
    return longest / len(words)


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

    # 3. Titre largement recouvert par une repetition
    if _duplicate_run_share(title) >= _DUPLICATE_RUN_MIN_SHARE:
        score -= 0.7

    return max(0.0, score)


def should_drop(ref: ImportedRef, threshold: float = 0.4) -> bool:
    """True si la ref doit etre droppee (score sous seuil).

    Un DOI resolvable prime sur toute heuristique typographique : il designe
    une oeuvre enregistree, et le titre reste rattrapable par resolution. Ce
    scoring ne juge que la coherence d'un titre — il n'a pas autorite pour
    supprimer une reference qui porte deja son identifiant.
    """
    if ref.url and _doi_from_url(ref.url):
        return False
    return syntactic_score(ref) < threshold
