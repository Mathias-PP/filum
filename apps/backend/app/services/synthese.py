"""Synthese ancree : chaque phrase renvoie a un extrait verbatim de la fiche, verifie avant pose.

Etude du 2026-09-14 : sur 14 modeles, 39 a 77 % seulement des faits cites
figurent dans la source citee, et la part baisse quand la recherche s'allonge.
Les systemes les mieux notes (Ai2 Scholar QA, OpenScholar) extraient les
citations avant d'ecrire et verifient apres. Philum a mieux qu'une citation
extraite : un extrait retrouve mot pour mot dans une source archivee.

La synthese d'une fiche s'ecrit donc phrase par phrase, chaque phrase finissant
par un ou plusieurs renvois `[extrait:<id>]`. Avant d'etre posee, elle est
verifiee :

- chaque phrase porte au moins un renvoi (un titre de section `#` n'en demande
  pas) ;
- chaque renvoi designe un extrait de cette fiche, retrouve dans sa source ;
- quand les embeddings repondent, la phrase est proche par le sens d'au moins un
  des extraits qu'elle cite, sous le seuil mesure pour la recherche d'extraits.

Une synthese qui echoue n'est pas posee : elle revient au modele avec la liste
des phrases a corriger. Ce qui est pose est vrai par construction, a la
proximite de sens pres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.services import embeddings
from app.services.excerpt_search import SIMILARITE_MINIMALE

RENVOI = re.compile(r"\[extrait:([0-9a-fA-F-]{36})\]")
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?…])\s+(?=\S)")

#: Statuts d'un extrait qui valent « retrouve dans sa source ». `None` : pose
#: avant que la relecture ne marque les extraits, ancre a l'ecriture malgre tout.
_RETROUVES = (None, "found", "moved")


@dataclass(frozen=True)
class Phrase:
    texte: str
    renvois: list[str]


@dataclass(frozen=True)
class Probleme:
    rang: int
    phrase: str
    raison: str


def decouper(texte: str) -> list[Phrase]:
    """Les phrases de la synthese et leurs renvois. Fonction pure.

    Un bloc de texte suivi de renvois est coupe en phrases : seule la derniere
    porte les renvois, les precedentes n'en ont pas et le diront. Les lignes de
    titre (`#`) ne sont pas des phrases.
    """
    phrases: list[Phrase] = []
    for ligne in texte.splitlines():
        propre = ligne.strip()
        if not propre or propre.startswith("#"):
            continue
        debut = 0
        morceaux: list[tuple[str, list[str]]] = []
        for renvoi in RENVOI.finditer(propre):
            avant = propre[debut : renvoi.start()].strip()
            if avant or not morceaux:
                morceaux.append((avant, []))
            morceaux[-1][1].append(renvoi.group(1).lower())
            debut = renvoi.end()
        reste = propre[debut:].strip()
        if reste:
            morceaux.append((reste, []))
        for bloc, renvois in morceaux:
            sous = [s.strip() for s in _FIN_DE_PHRASE.split(bloc) if s.strip()] or [""]
            for rang, sous_phrase in enumerate(sous):
                derniere = rang == len(sous) - 1
                if sous_phrase or renvois:
                    phrases.append(Phrase(sous_phrase, list(renvois) if derniere else []))
    return [p for p in phrases if p.texte]


def _similarite(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def verifier(
    db: AsyncSession, creator_id: UUID, slug: str, texte: str
) -> tuple[list[Phrase], list[Probleme], bool]:
    """Les phrases, les problemes a corriger, et si le soutien par le sens a pu etre verifie."""
    card = await db.scalar(
        select(BiblioCard).where(
            BiblioCard.user_id == creator_id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    phrases = decouper(texte)
    if card is None:
        return phrases, [Probleme(0, "", "Fiche introuvable.")], False
    resultat = await db.execute(
        select(Source)
        .options(selectinload(Source.excerpts))
        .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    extraits = {str(e.id).lower(): e for source in resultat.scalars() for e in source.excerpts}

    problemes: list[Probleme] = []
    if not phrases:
        problemes.append(Probleme(0, "", "La synthèse est vide."))
    for rang, phrase in enumerate(phrases, start=1):
        if not phrase.renvois:
            problemes.append(
                Probleme(
                    rang, phrase.texte, "phrase sans extrait : ajoute [extrait:<id>] ou retire-la"
                )
            )
            continue
        for renvoi in phrase.renvois:
            extrait = extraits.get(renvoi)
            if extrait is None:
                problemes.append(
                    Probleme(
                        rang,
                        phrase.texte,
                        f"[extrait:{renvoi}] n'est pas un extrait de cette fiche",
                    )
                )
            elif extrait.verified_status not in _RETROUVES:
                problemes.append(
                    Probleme(
                        rang, phrase.texte, f"[extrait:{renvoi}] n'est plus retrouvé dans sa source"
                    )
                )

    soutien_verifie = False
    a_juger = [p for p in phrases if p.renvois and all(r in extraits for r in p.renvois)]
    if a_juger:
        textes_extraits = sorted({r for p in a_juger for r in p.renvois})
        vecteurs = await embeddings.embed(
            [p.texte for p in a_juger]
            + [
                "\n".join(x for x in (extraits[r].context, extraits[r].text) if x)
                for r in textes_extraits
            ]
        )
        if vecteurs is not None:
            soutien_verifie = True
            par_extrait = dict(zip(textes_extraits, vecteurs[len(a_juger) :], strict=True))
            for phrase, vecteur in zip(a_juger, vecteurs[: len(a_juger)], strict=True):
                meilleur = max(_similarite(vecteur, par_extrait[r]) for r in phrase.renvois)
                if meilleur < SIMILARITE_MINIMALE:
                    rang = phrases.index(phrase) + 1
                    problemes.append(
                        Probleme(
                            rang,
                            phrase.texte,
                            "la phrase ne dit pas ce que disent les extraits cités : "
                            "reformule au plus près du passage ou cite un autre extrait",
                        )
                    )
    return phrases, problemes, soutien_verifie
