"""Relecture d'une fiche : ce qui manque encore, et quelle etape le comble.

Le deroule s'arretait apres les positions, meme quand la fiche portait une
source sans extrait, une source citee sans position ou aucune nuance. La grille
nomme ces manques un par un, chacun avec l'etape qui sait le combler ; le
deroule relance ces etapes tant qu'une relecture en comble au moins un.

Tout est compte sur la base, sans modele : une grille qui dependrait d'un
modele se laisserait convaincre, un compte non.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source, SourceStance
from app.services import couverture
from app.services.card_link import parse_public_card_path

SOUS_QUESTION_VIDE = "sous_question_vide"
SOURCE_SANS_EXTRAIT = "source_sans_extrait"
SOURCE_SANS_POSITION = "source_sans_position"
POSITION_SANS_APPUI = "position_sans_appui"
SANS_NUANCE = "sans_nuance"
RETRACTATION = "retractation"

#: Manques qu'une etape du deroule sait combler avec ses outils. Une
#: sous-question vide ne l'est plus ici : les passes d'exploration se sont deja
#: arretees faute de la couvrir. Une position sans appui ne se corrige pas par
#: un outil (une position exige un extrait) : elle est dite au bilan.
COMBLABLES: frozenset[str] = frozenset(
    {SOURCE_SANS_EXTRAIT, SOURCE_SANS_POSITION, SANS_NUANCE, RETRACTATION}
)


@dataclass(frozen=True)
class Manque:
    genre: str
    #: Ce qui manque : la sous-question, la source (titre et identifiant) ou la fiche.
    cible: str
    #: L'etape du deroule qui le comble : "exploration" ou "positions".
    etape: str


def _nom(source: Source) -> str:
    return f"{source.title or source.url} (source_id={source.id})"


async def grille(db: AsyncSession, creator_id: UUID, slug: str) -> list[Manque]:
    """Les manques de la fiche `slug` du createur, dans l'ordre ou les combler."""
    card = await db.scalar(
        select(BiblioCard).where(
            BiblioCard.user_id == creator_id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    if card is None:
        return []
    resultat = await db.execute(
        select(Source)
        .options(selectinload(Source.excerpts))
        .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
        .order_by(Source.position)
        .execution_options(populate_existing=True)
    )
    sources = list(resultat.scalars())

    manques: list[Manque] = []
    etat = await couverture.calculer(db, creator_id, slug)
    if etat is not None:
        manques += [Manque(SOUS_QUESTION_VIDE, q, "exploration") for q in etat.vides()]

    for source in sources:
        if not source.excerpts:
            # Un lien vers une autre fiche Philum est une connexion : ses
            # extraits vivent dans la fiche liee.
            if parse_public_card_path(source.url):
                continue
            manques.append(Manque(SOURCE_SANS_EXTRAIT, _nom(source), "exploration"))
            if source.stance:
                manques.append(Manque(POSITION_SANS_APPUI, _nom(source), "positions"))
            continue
        if not source.stance:
            manques.append(Manque(SOURCE_SANS_POSITION, _nom(source), "positions"))
        elif source.retraction_status == "retracted" and source.stance == SourceStance.APPUIE.value:
            manques.append(Manque(RETRACTATION, _nom(source), "positions"))

    citees = [source for source in sources if source.excerpts]
    if citees and not any(s.stance == SourceStance.NUANCE_CONTREDIT.value for s in citees):
        manques.append(Manque(SANS_NUANCE, card.title, "exploration"))
    return manques
