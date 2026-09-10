"""Rafraichit les avis de retractation, et y attache leur motif.

    uv run python -m app.scripts.motifs_retractation

Deux manques que cette passe comble, et qu'aucun autre chemin ne comble.

**Les brouillons ne sont jamais reverifies.** Le rafraichissement paresseux de
`services/source_enrichment.py` se declenche quand une fiche *publique* est
servie. Une fiche en cours d'ecriture, celle ou le createur decide encore quoi
citer, garde donc le verdict de sa creation. C'est exactement la fiche ou une
retractation tombee entre-temps compte le plus.

**Le motif n'arrive par nulle part ailleurs.** Crossref ne le rend pas, et le
jeu Retraction Watch ne s'interroge pas par DOI : il se telecharge en entier ou
pas du tout. Le demander a chaque source couterait 66 Mo par source ; il est
donc telecharge une fois par passe, et applique a tout le corpus.

Rejouable sans dommage. `--limit` borne le nombre d'appels a Crossref pour ne
pas le marteler ; le passage suivant reprendra les sources restantes. `--motifs-
seulement` saute entierement l'etage Crossref quand on ne veut que les motifs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.db.database import async_session_maker
from app.extractors.retraction_watch import motif_pour, telecharger_dump
from app.models.source import Source
from app.services.source_enrichment import enrich_one, needs_recheck

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("motifs")

#: Crossref n'affiche pas de quota dur, mais une passe de rattrapage n'a aucune
#: raison de vider le corpus d'un coup. Le passage suivant prendra la suite.
LIMITE = 200


async def rafraichir(limite: int) -> int:
    """Rejoue le controle sur les sources dont le verdict a vieilli.

    Le meme `needs_recheck` que le chemin paresseux : deux regles de peremption
    divergeraient, et c'est la plus laxiste qui deciderait de ce que le lecteur
    voit.
    """
    ecrits = 0
    async with async_session_maker() as db:
        sources = list((await db.execute(select(Source))).scalars())
        perimees = [
            s
            for s in sources
            if needs_recheck(s.retraction_checked_at, s.retraction_status, s.doi)
            or needs_recheck(s.oa_checked_at, s.oa_status, s.doi)
        ][:limite]
        logger.info("%s sources en base, %s a reverifier", len(sources), len(perimees))

        for source in perimees:
            valeurs = await enrich_one(source.doi)
            if not valeurs:
                continue
            for champ, valeur in valeurs.items():
                setattr(source, champ, valeur)
            ecrits += 1
        await db.commit()
    return ecrits


async def poser_les_motifs() -> tuple[int, int]:
    """Attache a chaque source sous avis le motif que Retraction Watch en donne.

    Rend `(motifs_poses, sources_sous_avis)`. Une source dont le statut ne
    correspond a aucun avis du jeu garde son motif a `NULL` : mieux vaut ne
    rien dire que de coller le motif d'une correction sous un badge de
    retractation.
    """
    index = await telecharger_dump()
    if index is None:
        logger.error("Jeu Retraction Watch indisponible, aucun motif pose")
        return 0, 0
    logger.info("%s articles connus de Retraction Watch", len(index))

    poses = 0
    async with async_session_maker() as db:
        sous_avis = [
            s
            for s in (await db.execute(select(Source))).scalars()
            if s.doi and s.retraction_status in {"retracted", "concern", "corrected"}
        ]
        for source in sous_avis:
            avis = index.get((source.doi or "").strip().lower())
            if not avis:
                continue
            motif = motif_pour(avis, source.retraction_status)
            if motif and motif != source.retraction_reason:
                source.retraction_reason = motif
                poses += 1
        await db.commit()
    return poses, len(sous_avis)


async def _tout(limite: int, motifs_seulement: bool) -> None:
    if not motifs_seulement:
        logger.info("%s verdicts rafraichis", await rafraichir(limite))
    poses, sous_avis = await poser_les_motifs()
    logger.info("%s motifs poses sur %s sources sous avis", poses, sous_avis)


def main() -> None:
    parser = argparse.ArgumentParser(description="Avis de retractation et leurs motifs.")
    parser.add_argument("--limit", type=int, default=LIMITE)
    parser.add_argument("--motifs-seulement", action="store_true")
    args = parser.parse_args()
    asyncio.run(_tout(args.limit, args.motifs_seulement))


if __name__ == "__main__":
    main()
