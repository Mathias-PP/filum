"""Planification des verifications de retractation, hors du cycle de reponse.

Le projet n'a pas d'ordonnanceur : la verification se declenche a la creation
d'une source, au changement de son DOI, et paresseusement quand une fiche
publique est servie avec des sources jamais verifiees. Ce dernier cas est ce
qui donne un badge aux dizaines de milliers de sources creees avant que la
colonne existe -- sans quoi la fonctionnalite ne servirait qu'au futur.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update

from app.db.database import async_session_maker
from app.extractors.retraction import check_retraction
from app.models.source import Source

logger = logging.getLogger(__name__)

# La boucle d'evenements ne garde qu'une reference FAIBLE sur les taches : sans
# cet ensemble, un create_task() peut etre collecte en vol et le travail perdu.
_background_tasks: set[asyncio.Task] = set()

# Une fiche publique populaire est servie des dizaines de fois par minute. Sans
# ce garde-fou, chaque requete relancerait la meme verification tant que la
# premiere n'a pas commit.
_in_flight: set[UUID] = set()


async def _run(pairs: list[tuple[UUID, str | None]]) -> None:
    """Interroge Crossref source par source, puis persiste chaque verdict.

    Sequentiel a dessein : un import cree jusqu'a 150 sources d'un seul clic,
    et Crossref n'a aucune raison d'encaisser 150 requetes simultanees pour
    autant. Le lecteur attend un badge sur une page publique, pas une reponse
    dans la seconde.
    """
    try:
        async with async_session_maker() as db:
            for source_id, doi in pairs:
                try:
                    result = await check_retraction(doi)
                except Exception as e:  # check_retraction ne leve pas : ceinture et bretelles
                    logger.warning("retraction check crashed for source=%s: %s", source_id, e)
                    continue
                await db.execute(
                    update(Source)
                    .where(Source.id == source_id)
                    .values(
                        retraction_status=result.status.value,
                        retraction_notice_doi=result.notice_doi,
                        retraction_checked_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
            await db.commit()
    finally:
        _in_flight.difference_update(sid for sid, _ in pairs)


def schedule_retraction_checks(pairs: list[tuple[UUID, str | None]]) -> None:
    """Lance la verification en tache de fond. Ne bloque jamais l'appelant.

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
