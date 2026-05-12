from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, ArchiveStatus

logger = logging.getLogger(__name__)


class WaybackService:
    BASE_URL = "https://archive.org/wayback/available"
    TIMEOUT = 30.0

    def __init__(self, db: AsyncSession, api_key: str | None = None):
        self._db = db
        self._api_key = api_key

    async def archive_url(self, source_id: UUID, url: str) -> dict:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            try:
                params = {"url": url}
                if self._api_key:
                    params["api_key"] = self._api_key

                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("archived_snapshots", {}).get("closest"):
                    archive_data = data["archived_snapshots"]["closest"]
                    archive_url = archive_data.get("url")
                    archive_timestamp = archive_data.get("timestamp")

                    if archive_timestamp:
                        archive_timestamp_dt = datetime.strptime(
                            archive_timestamp[:14], "%Y%m%d%H%M%S"
                        )
                    else:
                        archive_timestamp_dt = datetime.now()

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

                await self._update_source(source_id, ArchiveStatus.FAILED, None, None)
                return {"status": "failed", "reason": "no_archive_found"}

            except httpx.TimeoutException:
                logger.warning(f"Wayback timeout for {url}")
                await self._update_source(source_id, ArchiveStatus.PENDING, None, None)
                return {"status": "pending", "reason": "timeout"}

            except Exception as e:
                logger.error(f"Wayback error for {url}: {e}")
                await self._update_source(source_id, ArchiveStatus.FAILED, None, None)
                return {"status": "failed", "reason": str(e)}

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
            r if not isinstance(r, Exception) else {"status": "error", "error": str(r)}
            for r in results
        ]
