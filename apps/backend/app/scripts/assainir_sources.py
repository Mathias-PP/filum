"""Reapplique aux sources deja en base la regle des titres et des auteurs.

    uv run python -m app.scripts.assainir_sources                       # liste, n'ecrit rien
    uv run python -m app.scripts.assainir_sources --ecrire              # corrige
    uv run python -m app.scripts.assainir_sources --ecrire --resoudre   # et retrouve les titres

`Source` applique `core/champs_bibliographiques.py` a chaque affectation :
plus rien ne peut inscrire un titre de page anti-bot, un segment d'adresse ou
un profil en guise d'auteur. Mais la regle ne s'applique qu'a l'ecriture ; les
lignes posees avant elle gardent leur valeur tant qu'on ne la reecrit pas.
Cette passe les reecrit.

Un titre refuse devient vide. Avec `--resoudre`, la source est d'abord relue a
son origine (Crossref quand elle a un DOI, la page sinon) et le titre retrouve,
s'il passe la regle, prend la place du faux. Rejouable sans dommage.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.champs_bibliographiques import auteurs_bibliographiques, titre_bibliographique
from app.db.database import async_session_maker
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.services import metadonnees_source

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("assainir")


@dataclass(frozen=True)
class Correction:
    fiche: str
    source_id: str
    titre_avant: str | None
    titre_apres: str | None
    auteurs_avant: str | None
    auteurs_apres: str | None


async def _relire(source: Source) -> tuple[str | None, str | None]:
    """Le titre et les auteurs que l'origine de la source rend, passes a la regle."""
    origine = "crossref" if source.doi else "page"
    try:
        meta = await metadonnees_source.resoudre(origine, url=source.url, doi=source.doi)
    except metadonnees_source.OrigineIndisponibleError:
        return None, None
    if meta is None:
        return None, None
    return (
        titre_bibliographique(meta.title, source.url),
        auteurs_bibliographiques(meta.authors),
    )


async def assainir(db: AsyncSession, *, ecrire: bool, resoudre: bool) -> list[Correction]:
    lignes = (
        await db.execute(
            select(Source, BiblioCard.slug)
            .join(BiblioCard, BiblioCard.id == Source.biblio_card_id)
            .where(Source.deleted_at.is_(None))
            .order_by(BiblioCard.slug, Source.position)
        )
    ).all()
    corrections: list[Correction] = []
    for source, slug in lignes:
        titre = titre_bibliographique(source.title, source.url)
        auteurs = auteurs_bibliographiques(source.authors)
        if titre == source.title and auteurs == source.authors:
            continue
        if resoudre and (titre is None and source.title or auteurs is None and source.authors):
            relu_titre, relus_auteurs = await _relire(source)
            titre = titre or relu_titre
            auteurs = auteurs or relus_auteurs
        corrections.append(
            Correction(slug, str(source.id), source.title, titre, source.authors, auteurs)
        )
        if ecrire:
            source.title = titre
            source.authors = auteurs
    if ecrire:
        await db.commit()
    return corrections


async def _main(ecrire: bool, resoudre: bool) -> None:
    async with async_session_maker() as db:
        corrections = await assainir(db, ecrire=ecrire, resoudre=resoudre)
    for c in corrections:
        logger.info(
            "%s | %s | titre %r -> %r | auteurs %r -> %r",
            c.fiche,
            c.source_id,
            c.titre_avant,
            c.titre_apres,
            c.auteurs_avant,
            c.auteurs_apres,
        )
    verbe = "corrigees" if ecrire else "a corriger (relancer avec --ecrire)"
    logger.info("%s sources %s", len(corrections), verbe)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecrire", action="store_true", help="ecrire les corrections")
    parser.add_argument(
        "--resoudre", action="store_true", help="relire l'origine pour retrouver un titre refuse"
    )
    arguments = parser.parse_args()
    asyncio.run(_main(arguments.ecrire, arguments.resoudre))
