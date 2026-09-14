"""Des passages exacts de la page, classes par le sens pour chaque question.

Mesure du 2026-09-13 : 79 extraits refuses sur 83 avec un modele de 8
milliards de parametres, qui recopiait mal ou reformulait. Ici le serveur
decoupe la page et rend, pour chaque question, les passages les plus proches
par le sens. Le modele ne recopie plus : il choisit. Chaque passage rendu est
une tranche exacte de la page, donc `add_excerpt` l'accepte tel quel.

Sans service d'embeddings (developpement, panne), le classement par mots
communs de `passages_proches` prend le relais : moins fin, jamais vide a tort.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services import embeddings
from app.services.chunker import Unite, chunk_text
from app.services.excerpt_insertion import passages_proches

#: Taille visee d'un passage candidat, en caracteres. Meme ordre que la longueur
#: d'un extrait qui porte un raisonnement (80 a 160 mots) : le decoupage
#: accumule des phrases entieres jusqu'a la depasser.
TAILLE_PASSAGE = 600

#: Plafond d'`add_excerpt`. Un passage plus long est coupe a la derniere fin de
#: phrase qui tient dessous : un debut de passage reste un verbatim.
_LONGUEUR_MAX_EXTRAIT = 1000

#: Proximite de sens en dessous de laquelle un passage ne repond pas a la
#: question. Seuil mesure en production pour la recherche d'extraits par le sens.
SEUIL_SENS = 0.60

#: Passages rendus par question. Borne de lisibilite de la reponse d'outil, pas
#: une borne editoriale : une page dense se reinterroge avec d'autres questions.
PASSAGES_PAR_QUESTION = 8


@dataclass(frozen=True)
class Candidat:
    question: str
    texte: str
    debut: int
    score: float
    methode: str


def _similarite(a: list[float], b: list[float]) -> float:
    # Les vecteurs d'`embeddings.embed` sont normes : le produit scalaire vaut
    # la similarite cosinus.
    return sum(x * y for x, y in zip(a, b, strict=True))


def _borner(texte: str) -> str:
    if len(texte) <= _LONGUEUR_MAX_EXTRAIT:
        return texte
    coupe = texte[:_LONGUEUR_MAX_EXTRAIT]
    fin = max(coupe.rfind(". "), coupe.rfind("? "), coupe.rfind("! "))
    if fin > 0:
        return coupe[: fin + 1]
    return coupe[: coupe.rfind(" ")] if " " in coupe else coupe


async def proposer(
    page_text: str, questions: list[str], par_question: int = PASSAGES_PAR_QUESTION
) -> list[Candidat]:
    """Pour chaque question, les passages de la page qui y repondent, du plus proche au moins proche."""
    questions = [q.strip() for q in questions if q and q.strip()]
    if not page_text.strip() or not questions:
        return []
    morceaux = [m for m in chunk_text(page_text, TAILLE_PASSAGE, Unite.CARACTERES) if m.text]
    if not morceaux:
        return []

    vecteurs = await embeddings.embed([m.text for m in morceaux] + questions)
    if vecteurs is None:
        rendus: list[Candidat] = []
        for question in questions:
            for passage in passages_proches(page_text, question, limite=par_question):
                rendus.append(Candidat(question, passage, page_text.find(passage), 0.0, "mots"))
        return rendus

    passages, cibles = vecteurs[: len(morceaux)], vecteurs[len(morceaux) :]
    rendus = []
    for question, cible in zip(questions, cibles, strict=True):
        notes = sorted(
            ((_similarite(v, cible), m) for v, m in zip(passages, morceaux, strict=True)),
            key=lambda note: note[0],
            reverse=True,
        )
        for score, morceau in notes[:par_question]:
            if score < SEUIL_SENS:
                break
            texte = _borner(page_text[morceau.start : morceau.end].strip())
            debut = page_text.find(texte, morceau.start)
            rendus.append(Candidat(question, texte, debut, round(score, 3), "sens"))
    return rendus
