"""Fusionner les candidates de plusieurs moteurs en une seule liste classee.

Chaque moteur a son angle mort : la recherche web rate les articles derriere un
index academique, OpenAlex rate la presse, Europe PMC ne voit que le biomedical.
Les classements ne sont pas comparables entre eux (scores de natures
differentes), d'ou la fusion par rangs reciproques : une source que plusieurs
moteurs placent haut passe devant, sans qu'aucun score brut ne soit compare.

La constante 60 est celle de la publication d'origine (Cormack, Clarke et
Buettcher, SIGIR 2009), reprise telle quelle par la plupart des moteurs hybrides.
"""

from __future__ import annotations

from app.extractors.recherche_litterature import Candidate
from app.services.content_identity import extract_doi, normalize_url

CONSTANTE_RRF = 60


def identite(candidate: Candidate) -> str:
    """La meme source sous deux adresses a la meme identite : le DOI d'abord."""
    doi = candidate.doi or extract_doi(candidate.url)
    if doi:
        return f"doi:{doi.lower()}"
    return f"url:{normalize_url(candidate.url) or candidate.url}"


def fusionner(listes: list[list[Candidate]]) -> list[Candidate]:
    """Les candidates de toutes les listes, dedoublonnees et classees par rangs reciproques."""
    scores: dict[str, float] = {}
    retenues: dict[str, Candidate] = {}
    for liste in listes:
        for rang, candidate in enumerate(liste, start=1):
            cle = identite(candidate)
            scores[cle] = scores.get(cle, 0.0) + 1.0 / (CONSTANTE_RRF + rang)
            deja = retenues.get(cle)
            if deja is None:
                retenues[cle] = candidate
                continue
            _completer(deja, candidate)
    return sorted(retenues.values(), key=lambda c: scores[identite(c)], reverse=True)


def _completer(cible: Candidate, autre: Candidate) -> None:
    """Ce qu'un moteur sait et que l'autre ignore, sans ecraser ce qui est connu."""
    for champ in (
        "titre",
        "annee",
        "doi",
        "auteurs",
        "revue",
        "citations",
        "acces_libre_url",
        "type",
        "passage",
    ):
        if getattr(cible, champ) in (None, "") and getattr(autre, champ) not in (None, ""):
            setattr(cible, champ, getattr(autre, champ))
    for source in autre.sources:
        if source not in cible.sources:
            cible.sources.append(source)
    for raison in autre.raisons:
        if raison not in cible.raisons:
            cible.raisons.append(raison)
