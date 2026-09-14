"""Couverture d'une fiche par les sous-questions de son plan.

Une fiche repond a une question, et une reponse complete en traite chaque
aspect. Le plan liste ces aspects en sous-questions ; la couverture compte,
pour chacune, les extraits de la fiche qui l'eclairent. Elle decide si
l'exploration continue (une passe qui couvre une sous-question jusque-la vide
en appelle une autre) et montre au createur ce qui manque encore.

Le plan vit dans le workspace du createur, `runs/<slug>/plan.md`, une
sous-question par ligne commencant par « - » : lisible, et corrigeable a la main.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.services import agent_workspace, embeddings
from app.services.excerpt_insertion import PART_MOTS_COMMUNS
from app.services.excerpt_search import SIMILARITE_MINIMALE

_MOT = re.compile(r"\w+")


@dataclass(frozen=True)
class SousQuestion:
    texte: str
    #: Extraits de la fiche rattaches a cette sous-question.
    extraits: int
    #: Sources distinctes qui portent ces extraits.
    sources: int


@dataclass(frozen=True)
class Couverture:
    slug: str
    sous_questions: list[SousQuestion]
    sources_sans_extrait: int
    extraits: int

    def vides(self) -> list[str]:
        """Les sous-questions qu'aucun extrait n'eclaire encore, dans l'ordre du plan."""
        return [q.texte for q in self.sous_questions if q.extraits == 0]

    def en_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "sous_questions": [
                {"texte": q.texte, "extraits": q.extraits, "sources": q.sources}
                for q in self.sous_questions
            ],
            "sources_sans_extrait": self.sources_sans_extrait,
            "extraits": self.extraits,
        }


def chemin_plan(slug: str) -> str:
    return f"runs/{slug}/plan.md"


async def lire_plan(db: AsyncSession, creator_id: UUID, slug: str) -> list[str]:
    fichier = await agent_workspace.lire(db, creator_id, chemin_plan(slug))
    if fichier is None:
        return []
    return [
        ligne[2:].strip()
        for ligne in fichier.content.splitlines()
        if ligne.startswith("- ") and ligne[2:].strip()
    ]


async def ecrire_plan(
    db: AsyncSession, creator_id: UUID, slug: str, sous_questions: list[str]
) -> list[str]:
    """Remplace le plan de la fiche. Rend les sous-questions retenues, sans doublon."""
    propres: list[str] = []
    for brute in sous_questions:
        texte = " ".join(str(brute).split())
        if texte and texte not in propres:
            propres.append(texte)
    if not propres:
        raise ValueError("Un plan porte au moins une sous-question.")
    contenu = "# Plan de couverture\n\n" + "".join(f"- {q}\n" for q in propres)
    await agent_workspace.ecrire(db, creator_id, chemin_plan(slug), contenu)
    return propres


def _mots(texte: str) -> set[str]:
    return {m.lower() for m in _MOT.findall(texte) if len(m) > 2}


def _par_mots(texte: str, questions: list[str]) -> int | None:
    mots = _mots(texte)
    meilleur: int | None = None
    part_max = 0.0
    for rang, question in enumerate(questions):
        attendus = _mots(question)
        if not attendus:
            continue
        part = len(attendus & mots) / len(attendus)
        if part > part_max:
            meilleur, part_max = rang, part
    return meilleur if part_max >= PART_MOTS_COMMUNS else None


async def rattacher(textes: list[str], questions: list[str]) -> list[int | None]:
    """Pour chaque texte, le rang de la sous-question qu'il eclaire le mieux, ou None.

    Par le sens quand les embeddings repondent, sous le seuil mesure pour la
    recherche d'extraits ; sinon par mots communs. Un extrait sans rapport avec
    le plan ne couvre rien : le rattacher quand meme a la moins eloignee ferait
    croire couverte une sous-question que personne n'a documentee.
    """
    if not textes or not questions:
        return [None] * len(textes)
    vecteurs = await embeddings.embed(questions + textes)
    if vecteurs is None:
        return [_par_mots(texte, questions) for texte in textes]
    cibles, vus = vecteurs[: len(questions)], vecteurs[len(questions) :]
    rendus: list[int | None] = []
    for vecteur in vus:
        # Vecteurs normes : le produit scalaire vaut la similarite cosinus.
        notes = [sum(x * y for x, y in zip(vecteur, cible, strict=True)) for cible in cibles]
        meilleur = max(range(len(notes)), key=notes.__getitem__)
        rendus.append(meilleur if notes[meilleur] >= SIMILARITE_MINIMALE else None)
    return rendus


async def calculer(db: AsyncSession, creator_id: UUID, slug: str) -> Couverture | None:
    """La couverture de la fiche `slug` du createur, ou None si elle n'existe pas."""
    card = await db.scalar(
        select(BiblioCard).where(
            BiblioCard.user_id == creator_id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    if card is None:
        return None
    # `populate_existing` : l'agent pose des extraits dans la meme session, et une
    # collection chargee plus tot resterait figee sur son ancien contenu.
    resultat = await db.execute(
        select(Source)
        .options(selectinload(Source.excerpts))
        .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    sources = list(resultat.scalars())
    plan = await lire_plan(db, creator_id, slug)

    extraits = [
        (source.id, "\n".join(p for p in (extrait.context, extrait.text) if p))
        for source in sources
        for extrait in source.excerpts
    ]
    rangs = await rattacher([texte for _, texte in extraits], plan)
    comptes = [0] * len(plan)
    porteuses: list[set[UUID]] = [set() for _ in plan]
    for (source_id, _texte), rang in zip(extraits, rangs, strict=True):
        if rang is not None:
            comptes[rang] += 1
            porteuses[rang].add(source_id)

    return Couverture(
        slug=card.slug,
        sous_questions=[
            SousQuestion(texte=q, extraits=comptes[r], sources=len(porteuses[r]))
            for r, q in enumerate(plan)
        ],
        sources_sans_extrait=sum(1 for source in sources if not source.excerpts),
        extraits=len(extraits),
    )
