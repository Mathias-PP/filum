from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.models.source import ArchiveStatus, Source

logger = logging.getLogger(__name__)


class WaybackService:
    """Best-effort archiver against the Internet Archive Wayback Machine.

    Flow per URL:
      1. Trigger Save Page Now (SPN) via a GET to ``web.archive.org/save/<url>``.
         No API key required; rate-limited and slow but free. We fire and
         forget (timeout short, errors swallowed) — its only purpose is to
         *request* a fresh snapshot.
      2. Poll the `wayback/available` API with growing back-offs until either
         a snapshot is found or all attempts are exhausted. SPN typically
         finishes within 10–30 s for normal pages; we poll up to ~30 s.

    The previous version only queried `wayback/available` directly: that
    works for popular URLs already in the archive but silently fails for any
    fresh URL the user adds, which is most of the demo content. Adding the
    SPN trigger makes auto-archiving actually function for new pages.
    """

    AVAILABLE_URL = "https://archive.org/wayback/available"
    SAVE_URL = "https://web.archive.org/save"
    TIMEOUT = 30.0
    # Back-off schedule (seconds) for polling the snapshot after triggering
    # SPN. Sum ~33 s.
    POLL_DELAYS: tuple[float, ...] = (3.0, 5.0, 8.0, 8.0, 9.0)
    # Cadence des declenchements en lot. Save Page Now tolere quelques
    # requetes par minute pour un client anonyme ; au-dela il jette le lot.
    TRIGGER_GAP = 6.0
    # Pause entre deux consultations de l'API de disponibilite : elle est bien
    # plus permissive que SPN, mais 150 requetes d'affilee restent impolies.
    LOOKUP_GAP = 1.0

    def __init__(self, db: AsyncSession, api_key: str | None = None):
        self._db = db
        self._api_key = api_key

    async def archive_url(self, source_id: UUID, url: str) -> dict:
        # Refuse non-public URLs up-front so we don't ask the Internet
        # Archive to crawl loopback/private targets via this service. Source
        # creation now also blocks these at the API boundary (sources.py),
        # but defense-in-depth in case the source was inserted via seed or
        # an older client.
        if not url.strip():
            await self._update_source(source_id, ArchiveStatus.NOT_APPLICABLE, None, None)
            return {"status": "not_applicable", "reason": "no_url"}

        try:
            assert_url_is_safe(url)
        except UnsafeUrlError as e:
            logger.warning(f"Wayback skipped for non-public URL {url}: {e}")
            await self._update_source(source_id, ArchiveStatus.FAILED, None, None)
            return {"status": "failed", "reason": "unsafe_url"}

        # Step 1 — trigger Save Page Now (best effort).
        await self._trigger_save(url)

        # Step 2 — poll the availability API until we see a snapshot or run
        # out of retries.
        for delay in self.POLL_DELAYS:
            await asyncio.sleep(delay)
            found = await self._lookup_snapshot(url)
            if found is None:
                continue
            return await self._mark_archived(source_id, *found)

        # Aucun instantane apres le sondage. Ce n'est pas la preuve que l'URL
        # soit inarchivable : Save Page Now travaille en differe et peut avoir
        # simplement pris du retard. La source reste `pending`, et la reprise
        # paresseuse la reproposera.
        return {"status": "pending", "reason": "no_snapshot_yet"}

    async def _trigger_save(self, url: str) -> None:
        """Demande un instantane frais. N'attend pas qu'il soit produit."""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=False) as client:
                # GET works for SPN public endpoint. We don't care about the
                # response — only that the archive request was kicked off.
                await client.get(f"{self.SAVE_URL}/{url}")
        except Exception as e:  # noqa: BLE001 — best-effort, log and continue.
            logger.info(f"Wayback SPN trigger failed for {url} (will still poll): {e}")

    async def _lookup_snapshot(self, url: str) -> tuple[str, str | None] | None:
        """(url d'archive, horodatage) si un instantane existe, sinon None.

        Une panne du service et une absence d'instantane sont indistinguables
        ici, et c'est voulu : les deux laissent la source en attente.
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                params = {"url": url}
                if self._api_key:
                    params["api_key"] = self._api_key
                response = await client.get(self.AVAILABLE_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.warning(f"Wayback poll timeout for {url}")
            return None
        except Exception as e:  # noqa: BLE001 — transient, the caller retries.
            logger.info(f"Wayback poll error for {url}: {e}")
            return None

        snapshot = data.get("archived_snapshots", {}).get("closest")
        if not snapshot or not snapshot.get("url"):
            return None
        return snapshot["url"], snapshot.get("timestamp")

    async def _mark_archived(
        self, source_id: UUID, archive_url: str, archive_timestamp: str | None
    ) -> dict:
        if archive_timestamp:
            try:
                stamp = datetime.strptime(archive_timestamp[:14], "%Y%m%d%H%M%S")
            except ValueError:
                stamp = datetime.now().replace(tzinfo=None)
        else:
            stamp = datetime.now().replace(tzinfo=None)

        await self._update_source(source_id, ArchiveStatus.ARCHIVED, archive_url, stamp)
        return {"status": "archived", "archive_url": archive_url, "timestamp": stamp.isoformat()}

    async def archive_batch(self, sources: list[tuple[UUID, str]]) -> list[dict]:
        """Archive un lot en deux temps, a une cadence que SPN accepte.

        Declencher puis sonder source par source ne marche pas a l'echelle
        d'un import : 152 sondages de 33 s mis bout a bout tiendraient plus
        d'une heure, et 152 declenchements simultanes se font jeter. On
        declenche donc tout le lot d'abord, espace ; le temps que la derniere
        URL soit demandee, les premieres ont eu plusieurs minutes pour etre
        capturees. Les sondages suivent, un par URL.
        """
        results: list[dict] = []
        todo: list[tuple[UUID, str]] = []

        for source_id, url in sources:
            if not url.strip():
                # Pas d'URL : il n'y a rien a archiver. L'inscrire `failed`
                # affirmerait qu'on a essaye et que la page est perdue.
                await self._update_source(source_id, ArchiveStatus.NOT_APPLICABLE, None, None)
                results.append({"status": "not_applicable", "reason": "no_url"})
                continue
            try:
                assert_url_is_safe(url)
            except UnsafeUrlError as e:
                # Definitif : cette URL ne sera jamais archivable.
                logger.warning(f"Wayback skipped for non-public URL {url}: {e}")
                await self._update_source(source_id, ArchiveStatus.FAILED, None, None)
                results.append({"status": "failed", "reason": "unsafe_url"})
                continue
            todo.append((source_id, url))

        for i, (_, url) in enumerate(todo):
            if i:
                await asyncio.sleep(self.TRIGGER_GAP)
            await self._trigger_save(url)

        for i, (source_id, url) in enumerate(todo):
            if i:
                await asyncio.sleep(self.LOOKUP_GAP)
            found = await self._lookup_snapshot(url)
            if found is None:
                results.append({"status": "pending", "reason": "no_snapshot_yet"})
                continue
            results.append(await self._mark_archived(source_id, *found))

        return results

    async def _update_source(
        self,
        source_id: UUID,
        status: ArchiveStatus,
        archive_url: str | None,
        archive_timestamp: datetime | None,
    ) -> None:
        result = await self._db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source:
            source.archive_status = status
            source.archive_url = archive_url
            source.archive_timestamp = archive_timestamp
            await self._db.commit()

    async def archive_all_pending(self, sources: list[tuple[UUID, str]]) -> list[dict]:
        return await self.archive_batch(sources)


# La boucle d'evenements ne garde qu'une reference FAIBLE sur les taches : sans
# cet ensemble, un create_task() peut etre collecte en vol et le travail perdu.
_background_tasks: set[asyncio.Task] = set()

# Une fiche publique populaire est servie des dizaines de fois par minute, et
# la reprise paresseuse relancerait le meme archivage a chaque affichage.
_in_flight: set[UUID] = set()


async def _run_batch(pairs: list[tuple[UUID, str]]) -> None:
    from app.core.config import get_settings
    from app.db.database import async_session_maker

    try:
        async with async_session_maker() as db:
            await WaybackService(db, get_settings().wayback_api_key).archive_batch(pairs)
    except Exception as e:  # noqa: BLE001 — une tache de fond ne remonte a personne.
        logger.warning("Wayback batch crashed: %s", e)
    finally:
        _in_flight.difference_update(sid for sid, _ in pairs)


def schedule_archiving(pairs: list[tuple[UUID, str]]) -> None:
    """Archive en tache de fond, a cadence tenable. Ne bloque jamais l'appelant."""
    todo = [(sid, url) for sid, url in pairs if sid not in _in_flight]
    if not todo:
        return
    _in_flight.update(sid for sid, _ in todo)
    task = asyncio.create_task(_run_batch(todo))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
