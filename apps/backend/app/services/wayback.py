from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    def __init__(self, db: AsyncSession, api_key: str | None = None):
        self._db = db
        self._api_key = api_key

    async def archive_url(self, source_id: UUID, url: str) -> dict:
        # Step 1 — trigger Save Page Now (best effort).
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=False) as client:
                # GET works for SPN public endpoint. We don't care about the
                # response — only that the archive request was kicked off.
                await client.get(f"{self.SAVE_URL}/{url}")
        except Exception as e:  # noqa: BLE001 — best-effort, log and continue.
            logger.info(f"Wayback SPN trigger failed for {url} (will still poll): {e}")

        # Step 2 — poll the availability API until we see a snapshot or run
        # out of retries.
        for delay in self.POLL_DELAYS:
            await asyncio.sleep(delay)
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
                continue
            except Exception as e:  # noqa: BLE001 — keep polling on transient errors.
                logger.info(f"Wayback poll error for {url}: {e}")
                continue

            snapshot = data.get("archived_snapshots", {}).get("closest")
            if not snapshot:
                continue

            archive_url = snapshot.get("url")
            archive_timestamp = snapshot.get("timestamp")
            if not archive_url:
                continue

            if archive_timestamp:
                try:
                    archive_timestamp_dt = datetime.strptime(archive_timestamp[:14], "%Y%m%d%H%M%S")
                except ValueError:
                    archive_timestamp_dt = datetime.now().replace(tzinfo=None)
            else:
                archive_timestamp_dt = datetime.now().replace(tzinfo=None)

            await self._update_source(
                source_id,
                ArchiveStatus.ARCHIVED,
                archive_url,
                archive_timestamp_dt,
            )
            return {
                "status": "archived",
                "archive_url": archive_url,
                "timestamp": archive_timestamp_dt.isoformat(),
            }

        # All polls exhausted without finding a snapshot.
        await self._update_source(source_id, ArchiveStatus.FAILED, None, None)
        return {"status": "failed", "reason": "no_snapshot_after_poll"}

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
        tasks = [self.archive_url(source_id, url) for source_id, url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r if not isinstance(r, Exception) else {"status": "error", "error": str(r)}  # type: ignore[misc]
            for r in results
        ]
