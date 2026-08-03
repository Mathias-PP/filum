"""Enrichissement des sources par des services tiers, hors du cycle de reponse.

Deux verifications aujourd'hui, toutes deux a partir du DOI : l'avis de
retractation (Crossref) et l'acces libre (OpenAlex). Elles sont menees dans la
meme passe parce qu'elles se declenchent aux memes moments et sur les memes
sources -- deux ordonnanceurs feraient deux fois le travail de reveil, deux
transactions, et deux garde-fous a tenir en phase.

Le projet n'a pas d'ordonnanceur : l'enrichissement se declenche a la creation
d'une source, au changement de son DOI, et paresseusement quand une fiche
publique est servie avec des sources jamais enrichies. Ce dernier cas est ce
qui couvre les sources creees avant que les colonnes existent -- sans quoi la
fonctionnalite ne servirait qu'au futur.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update

from app.db.database import async_session_maker
from app.extractors.open_access import check_open_access
from app.extractors.retraction import check_retraction
from app.models.source import Source

logger = logging.getLogger(__name__)

# La boucle d'evenements ne garde qu'une reference FAIBLE sur les taches : sans
# cet ensemble, un create_task() peut etre collecte en vol et le travail perdu.
_background_tasks: set[asyncio.Task] = set()

# Une fiche publique populaire est servie des dizaines de fois par minute. Sans
# ce garde-fou, chaque requete relancerait le meme enrichissement tant que le
# premier n'a pas commit.
_in_flight: set[UUID] = set()


async def _enrich_one(doi: str | None) -> dict:
    """Valeurs a ecrire pour une source. Aucun appel ne leve.

    Un service muet ne doit pas emporter l'autre : une panne d'OpenAlex ne
    prive pas le lecteur du badge de retractation, et reciproquement.
    """
    values: dict = {}
    now = datetime.now(UTC).replace(tzinfo=None)

    try:
        retraction = await check_retraction(doi)
    except Exception as e:  # check_retraction ne leve pas : ceinture et bretelles
        logger.warning("retraction check crashed for doi=%s: %s", doi, e)
    else:
        values.update(
            retraction_status=retraction.status.value,
            retraction_notice_doi=retraction.notice_doi,
            retraction_checked_at=now,
        )

    try:
        oa = await check_open_access(doi)
    except Exception as e:
        logger.warning("open access check crashed for doi=%s: %s", doi, e)
    else:
        values.update(
            oa_status=oa.status.value,
            oa_url=oa.url,
            oa_license=oa.license,
            in_doaj=oa.in_doaj,
            oa_checked_at=now,
        )

    return values


async def _run(pairs: list[tuple[UUID, str | None]]) -> None:
    """Interroge les services source par source, puis persiste chaque verdict.

    Sequentiel a dessein : un import cree jusqu'a 150 sources d'un seul clic,
    et ni Crossref ni OpenAlex n'ont de raison d'encaisser 150 requetes
    simultanees pour autant. Le lecteur attend un badge sur une page publique,
    pas une reponse dans la seconde.
    """
    try:
        async with async_session_maker() as db:
            for source_id, doi in pairs:
                values = await _enrich_one(doi)
                if not values:
                    continue
                await db.execute(update(Source).where(Source.id == source_id).values(**values))
            await db.commit()
    finally:
        _in_flight.difference_update(sid for sid, _ in pairs)


def schedule_source_enrichment(pairs: list[tuple[UUID, str | None]]) -> None:
    """Lance l'enrichissement en tache de fond. Ne bloque jamais l'appelant.

    Les sources sans DOI sont incluses : leur verdict est « non verifiable »,
    date -- ce qui vaut mieux qu'un silence indistinguable de « pas encore
    verifie ».
    """
    todo = [(sid, doi) for sid, doi in pairs if sid not in _in_flight]
    if not todo:
        return
    _in_flight.update(sid for sid, _ in todo)
    task = asyncio.create_task(_run(todo))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
