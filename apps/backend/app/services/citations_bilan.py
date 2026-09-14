"""Les renvois de la réponse du bilan deviennent des liens vers les extraits de la fiche.

Perplexity, Scira et Morphic répondent avec des citations cliquables dans le
texte. Morphic y ajoute un contrat : le modèle ne peut citer que les étiquettes
que la recherche a rendues, jamais en inventer. Chez Philum, l'étiquette est
l'identifiant d'un extrait posé sur la fiche, retrouvé mot pour mot dans sa
source ; le contrat est tenu ici, par le serveur, et non par la consigne.

Le modèle écrit `[extrait:<id>]` après la phrase qu'un extrait soutient. Chaque
renvoi qui désigne un extrait de la fiche devient un lien numéroté vers cet
extrait ; un renvoi vers rien est retiré, et la réponse le dit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.biblio_card import BiblioCard
from app.models.source import Source

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

#: Un renvoi, sous les variantes qu'un modele ecrit en pratique : espaces autour
#: des deux-points, pluriel, plusieurs identifiants separes par une virgule ou un
#: point-virgule. Un renvoi mal reconnu restait affiche brut dans la reponse.
RENVOI = re.compile(rf"\s*\[\s*extraits?\s*:\s*({_UUID}(?:\s*[,;]\s*{_UUID})*)\s*\]", re.IGNORECASE)


@dataclass(frozen=True)
class ReponseLiee:
    texte: str
    cites: int
    retires: int


def lier_renvois(texte: str, extraits: set[str], adresse: str) -> ReponseLiee:
    """Remplace les renvois par des liens numérotés vers les extraits connus. Fonction pure.

    Un même extrait garde son numéro à chaque renvoi. `adresse` est la page de la
    fiche ; le lien vise l'ancre de l'extrait.
    """
    numeros: dict[str, int] = {}
    retires = 0

    def remplacer(m: re.Match[str]) -> str:
        nonlocal retires
        liens: list[str] = []
        for brut in re.findall(_UUID, m.group(1)):
            identifiant = brut.lower()
            if identifiant not in extraits:
                retires += 1
                continue
            numero = numeros.setdefault(identifiant, len(numeros) + 1)
            liens.append(f"[{numero}]({adresse}#extrait-{identifiant})")
        return " " + " ".join(liens) if liens else ""

    lie = RENVOI.sub(remplacer, texte)
    if retires:
        lie += (
            f"\n\n{retires} renvoi{'s' if retires > 1 else ''} retiré{'s' if retires > 1 else ''} : "
            "ils ne désignaient aucun extrait de la fiche."
        )
    return ReponseLiee(lie, len(numeros), retires)


async def lier(
    db: AsyncSession, creator_id: UUID, username: str, slug: str, texte: str
) -> ReponseLiee:
    """La réponse avec ses renvois vérifiés contre les extraits de la fiche et changés en liens."""
    card = await db.scalar(
        select(BiblioCard).where(
            BiblioCard.user_id == creator_id,
            BiblioCard.slug == slug,
            BiblioCard.deleted_at.is_(None),
        )
    )
    extraits: set[str] = set()
    if card is not None:
        resultat = await db.execute(
            select(Source)
            .options(selectinload(Source.excerpts))
            .where(Source.biblio_card_id == card.id, Source.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        extraits = {str(e.id).lower() for s in resultat.scalars() for e in s.excerpts}
    base = get_settings().frontend_base_url.rstrip("/")
    return lier_renvois(texte, extraits, f"{base}/@{username}/{slug}")
