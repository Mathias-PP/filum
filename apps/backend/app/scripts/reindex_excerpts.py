"""Rattrapage des vecteurs d'extraits, pour rendre l'existant cherchable.

`indexer_sans_bruit` ne s'execute qu'a l'enregistrement d'un extrait. Tout ce
qui a ete saisi avant que l'indexation existe n'a donc aucun vecteur, et reste
invisible a la recherche par le sens jusqu'a une modification qui n'a aucune
raison d'arriver. Sans ce rattrapage, la recherche repondrait « aucun extrait »
sur un corpus entier, ce qui est exactement le mensonge que la distinction
entre indisponible et vide cherche a eviter.

    uv run python -m app.scripts.reindex_excerpts

Rejouable sans dommage : `a_reindexer` compare l'empreinte du texte a celle
rangee a cote du vecteur, et ne redemande que ce qui manque ou a bouge. Un
second passage ne coute donc aucun appel au modele.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.db.database import async_session_maker
from app.models.source_excerpt import SourceExcerpt
from app.services.excerpt_indexing import indexer_extraits

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("reindex")

#: Un lot par transaction. Assez grand pour que les allers-retours ne dominent
#: pas, assez petit pour qu'une panne de service ne perde qu'un lot -- les
#: precedents sont deja valides et ne seront pas redemandes au passage suivant.
TAILLE_LOT = 64


async def reindexer_tout(taille_lot: int = TAILLE_LOT) -> tuple[int, int]:
    """Indexe tous les extraits qui n'ont pas de vecteur a jour.

    Rend `(nombre_ecrit, nombre_examine)`. S'arrete au premier lot ou le
    service ne repond pas : insister enchainerait les echecs sans rien ecrire,
    et le passage suivant reprendra exactement la ou celui-ci s'est arrete.
    """
    ecrits = 0
    examines = 0
    async with async_session_maker() as db:
        tous = list((await db.execute(select(SourceExcerpt))).scalars())
        logger.info("%s extraits en base", len(tous))

        for debut in range(0, len(tous), taille_lot):
            lot = tous[debut : debut + taille_lot]
            examines += len(lot)
            try:
                nombre = await indexer_extraits(db, lot)
            except Exception as e:
                await db.rollback()
                logger.error("Lot %s abandonne : %s", debut // taille_lot + 1, e)
                break

            if nombre:
                await db.commit()
                ecrits += nombre
                logger.info("Lot %s : %s vecteurs ecrits", debut // taille_lot + 1, nombre)
            else:
                # Zero peut vouloir dire « tout etait deja a jour » comme
                # « le service n'a pas repondu ». La seconde hypothese se
                # verifie au lot suivant : si rien ne s'ecrit jamais, les
                # journaux d'`indexer_extraits` le disent.
                logger.info("Lot %s : rien a faire", debut // taille_lot + 1)

    return ecrits, examines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taille-lot", type=int, default=TAILLE_LOT)
    args = parser.parse_args()

    ecrits, examines = asyncio.run(reindexer_tout(args.taille_lot))
    logger.info("Termine : %s vecteurs ecrits sur %s extraits examines", ecrits, examines)


if __name__ == "__main__":
    main()
