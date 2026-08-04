from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from typing import TypeVar
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.models.source import ArchiveStatus, Source

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ThrottledError(Exception):
    """Le service a refuse de repondre et demande qu'on ralentisse.

    Distinct d'une absence d'instantane. Confondre les deux revient a conclure
    sur une URL qu'on n'a jamais reussi a interroger -- la meme faute que
    d'inscrire `failed` faute d'avoir trouve a temps.
    """

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("throttled")
        self.retry_after = retry_after


class _Pacer:
    """Cadence qui s'ajuste au service au lieu de la deviner.

    On part du plancher, on double a chaque refus (en honorant un eventuel
    `Retry-After`), on redescend doucement quand les requetes repassent. Le
    temps d'attente cumule est plafonne : au-dela, le lot s'arrete et laisse le
    reste en attente plutot que de mobiliser la base indefiniment.
    """

    def __init__(self, floor: float, ceiling: float, budget: float) -> None:
        self._floor = floor
        self._ceiling = ceiling
        self._budget = budget
        self.gap = floor
        self.spent = 0.0

    @property
    def exhausted(self) -> bool:
        return self.spent >= self._budget

    async def pause(self) -> None:
        await asyncio.sleep(self.gap)
        self.spent += self.gap

    def slow_down(self, retry_after: float | None = None) -> None:
        self.gap = min(self._ceiling, max(self.gap * 2, retry_after or 0.0))

    def speed_up(self) -> None:
        self.gap = max(self._floor, self.gap * 0.8)


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
    # Planchers de cadence, pas cadences nominales : le rythme reel s'ajuste
    # aux refus du service (cf. _Pacer). Les limites d'archive.org ne sont pas
    # publiees et varient avec sa charge -- mesure en aout 2026, 6 s entre deux
    # declenchements se faisait encore refuser.
    TRIGGER_GAP = 6.0
    LOOKUP_GAP = 1.0
    # Plafonds : au-dela, insister ne sert plus a rien.
    TRIGGER_CEILING = 120.0
    LOOKUP_CEILING = 60.0
    # Tentatives par URL face a un refus.
    MAX_ATTEMPTS = 3
    # Temps d'attente cumule maximal d'un lot. Sans ce plafond, un archive.org
    # durablement indisponible ferait tenir la session base ouverte des heures
    # sur une VM d'un gigaoctet. Ce qui depasse reste `pending`, et la reprise
    # paresseuse le reproposera au prochain affichage de la fiche.
    BATCH_BUDGET = 900.0

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

    @staticmethod
    def _refusal(response: httpx.Response) -> ThrottledError | None:
        """Un refus de service, s'il y en a un.

        429 est explicite. Les 5xx le sont moins, mais un `523` de Cloudflare
        (origine injoignable) ou un `503` disent la meme chose : le service ne
        peut pas repondre maintenant, insister au meme rythme est inutile.
        """
        if response.status_code != 429 and response.status_code < 500:
            return None
        raw = response.headers.get("retry-after")
        try:
            return ThrottledError(float(raw) if raw else None)
        except ValueError:
            # `Retry-After` peut etre une date HTTP. On ignore la valeur et on
            # laisse le doublement de cadence faire son office.
            return ThrottledError()

    async def _trigger_save(self, url: str) -> None:
        """Demande un instantane frais. N'attend pas qu'il soit produit.

        Leve ``ThrottledError`` si le service refuse : l'appelant ralentit et
        reessaie, au lieu de bruler l'URL a la cadence qui vient d'echouer.
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=False) as client:
                # GET works for SPN public endpoint. We don't care about the
                # response body — only whether the request was accepted.
                response = await client.get(f"{self.SAVE_URL}/{url}")
        except Exception as e:  # noqa: BLE001 — best-effort, log and continue.
            logger.info(f"Wayback SPN trigger failed for {url} (will still poll): {e}")
            return

        refusal = self._refusal(response)
        if refusal is not None:
            raise refusal

    async def _lookup_snapshot(self, url: str) -> tuple[str, str | None] | None:
        """(url d'archive, horodatage) si un instantane existe, sinon None.

        Leve ``ThrottledError`` si le service a refuse de repondre : c'est le seul
        cas ou l'absence d'instantane ne veut rien dire. Une panne ou un
        timeout restent indistinguables d'une absence, et c'est assume -- les
        deux laissent la source en attente.
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                params = {"url": url}
                if self._api_key:
                    params["api_key"] = self._api_key
                response = await client.get(self.AVAILABLE_URL, params=params)
                refusal = self._refusal(response)
                if refusal is not None:
                    raise refusal
                response.raise_for_status()
                data = response.json()
        except ThrottledError:
            raise
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

    async def _attempt(self, pacer: _Pacer, call: Callable[[], Awaitable[T]]) -> T | None:
        """Execute `call` a la cadence du pacer, en reessayant les refus.

        Retourne None quand toutes les tentatives ont ete refusees. C'est une
        absence de reponse, pas une reponse negative : l'appelant doit laisser
        la source en attente et surtout pas la declarer en echec.
        """
        for _ in range(self.MAX_ATTEMPTS):
            if pacer.exhausted:
                return None
            await pacer.pause()
            try:
                result = await call()
            except ThrottledError as refusal:
                pacer.slow_down(refusal.retry_after)
                continue
            pacer.speed_up()
            return result
        return None

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

        pacer = _Pacer(self.TRIGGER_GAP, self.TRIGGER_CEILING, self.BATCH_BUDGET)
        for _, url in todo:
            if pacer.exhausted:
                break
            await self._attempt(pacer, partial(self._trigger_save, url))

        pacer = _Pacer(self.LOOKUP_GAP, self.LOOKUP_CEILING, self.BATCH_BUDGET)
        for source_id, url in todo:
            if pacer.exhausted:
                break
            found = await self._attempt(pacer, partial(self._lookup_snapshot, url))
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
