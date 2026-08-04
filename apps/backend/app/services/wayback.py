from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from html import unescape
from typing import Protocol, TypeVar
from urllib.parse import urljoin
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_safety import UnsafeUrlError, assert_url_is_safe
from app.models.source import ArchiveStatus, Source

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _Attemptable(Protocol):
    archive_attempted_at: datetime | None


_META_TAG = re.compile(rb"<meta\b[^>]*>", re.IGNORECASE)
_HTTP_EQUIV_REFRESH = re.compile(rb"""http-equiv\s*=\s*['"]?refresh\b""", re.IGNORECASE)
_CONTENT_ATTR = re.compile(rb"""content\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
# Le point-virgule ne borne pas l'URL : il n'y apparait qu'a l'interieur d'une
# entite (`&amp;`), et l'exclure coupait la cible en plein milieu de celle-ci.
_REFRESH_URL = re.compile(rb"""url\s*=\s*['"]?([^'"\s>]+)""", re.IGNORECASE)


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
        self._started = time.monotonic()
        self.gap = floor

    @property
    def spent(self) -> float:
        # Le temps ecoule, pas la somme des pauses : une requete peut durer
        # trente secondes et chaque refus est reessaye. Compter les seules
        # pauses laissait un lot tenir des heures sans jamais « depasser » son
        # budget -- qui ne protegeait donc pas ce qu'il pretendait proteger.
        return time.monotonic() - self._started

    @property
    def exhausted(self) -> bool:
        return self.spent >= self._budget

    async def pause(self) -> None:
        await asyncio.sleep(self.gap)

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
    # Second canal sur le meme index, limite independamment du premier.
    CDX_URL = "https://web.archive.org/cdx/search/cdx"
    SAVE_URL = "https://web.archive.org/save"
    TIMEOUT = 30.0
    # Le sondage attend plus longtemps que le reste : CDX cherche dans un index
    # de centaines de milliards de captures. Mesure depuis la VM le 2026-08-04,
    # trois appels de suite : 18,4 s, 18,7 s, 19,7 s pour une requete qui ne
    # renvoie rien. A 30 s, la moindre charge faisait echouer le sondage sur un
    # timeout -- et un timeout n'est pas une reponse, donc rien ne concluait.
    LOOKUP_TIMEOUT = 60.0
    # Resoudre une redirection est court : un resolveur repond ou ne repond
    # pas. Inutile d'immobiliser le lot longtemps pour ca.
    RESOLVE_TIMEOUT = 15.0
    MAX_REDIRECTS = 5
    # Une redirection se declare dans l'en-tete du document : inutile de
    # telecharger un article entier sur une VM d'un gigaoctet pour l'apprendre.
    PEEK_BYTES = 65_536
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

    async def _resolve(self, url: str) -> str:
        """L'URL de la ressource, pas celle du panneau qui y mene.

        Un resolveur -- `doi.org`, un raccourcisseur, un « linking hub »
        d'editeur -- n'a dans l'archive que des captures de redirection. Le
        sondage filtre sur `200` et ne trouve donc rien, et capturer une
        redirection ne preserve aucun contenu. Mesure le 2026-08-04 :
        `doi.org/10.1002/brb3.244` n'a que des `302`, sa cible Wiley a une
        capture `200`.

        **Une redirection reste une redirection quelle que soit sa forme.**
        `linkinghub.elsevier.com` repond `200` -- aucun client HTTP n'y voit
        une redirection -- avec un `<meta http-equiv="refresh">` et, pour tout
        contenu, le mot « Redirecting ». Les deux formes sont suivies.

        La detection est comportementale -- cette URL redirige-t-elle ? -- et
        jamais par liste de domaines, sans quoi le prochain resolveur
        repasserait au travers.

        Ne leve jamais et ne juge pas le code de reponse : les editeurs
        refusent les robots par un `403`, mais la redirection a deja eu lieu
        et l'URL finale est exacte. Ne pas savoir resoudre laisse l'URL telle
        quelle -- une ignorance, pas une reponse.
        """
        current = url
        seen: set[str] = set()
        for _ in range(self.MAX_REDIRECTS):
            peeked = await self._peek(current)
            if peeked is None:
                return current
            final, target = peeked
            if target is None:
                return final
            nxt = urljoin(final, target)
            if nxt == final or nxt in seen:
                return final
            seen.add(final)
            current = nxt
        return current

    async def _peek(self, url: str) -> tuple[str, str | None] | None:
        """(url finale HTTP, cible d'un meta refresh eventuel), ou None.

        Le corps n'est lu que sur ses premiers octets : une redirection se
        declare dans l'en-tete du document, et une VM d'un gigaoctet n'a pas a
        telecharger des articles entiers pour l'apprendre.
        """
        try:
            async with (
                httpx.AsyncClient(
                    timeout=self.RESOLVE_TIMEOUT,
                    follow_redirects=True,
                    max_redirects=self.MAX_REDIRECTS,
                ) as client,
                client.stream("GET", url) as response,
            ):
                final = str(response.url) or url
                if "html" not in response.headers.get("content-type", ""):
                    return final, None
                body = b""
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) >= self.PEEK_BYTES:
                        break
            return final, self._meta_refresh_target(body)
        except Exception as e:  # noqa: BLE001 — l'URL d'origine reste utilisable.
            logger.info("Resolve failed for %s: %s %s", url, type(e).__name__, e)
            return None

    @staticmethod
    def _meta_refresh_target(body: bytes) -> str | None:
        """La cible d'un `<meta http-equiv="refresh">`, s'il y en a une.

        Les deux conditions sont exigees sur la *meme* balise : un `content`
        contenant « url= » ne redirige rien s'il appartient a un
        `<meta name="citation_title">`.
        """
        for tag in _META_TAG.findall(body):
            if not _HTTP_EQUIV_REFRESH.search(tag):
                continue
            content = _CONTENT_ATTR.search(tag)
            if content is None:
                continue
            value = next(g for g in content.groups() if g is not None)
            target = _REFRESH_URL.search(value)
            if target is not None:
                # `&amp;` dans un attribut HTML est un `&` dans l'URL : sans
                # cela on sonderait une adresse qui n'existe pas.
                return unescape(target.group(1).strip().decode("utf-8", "replace"))
        return None

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

        Deux canaux interrogent le meme index. Mesure depuis la VM le
        2026-08-04, a la meme seconde et depuis la meme IP : `wayback/available`
        repondait 429 pendant que CDX repondait 200 avec l'instantane. La
        limitation porte sur le point d'entree, pas sur l'archive -- s'arreter
        au premier refus reviendrait a conclure sans avoir regarde.

        Leve ``ThrottledError`` seulement si *aucun* canal n'a pu se prononcer.
        Une absence n'est affirmee que sur une reponse saine.
        """
        refusal: ThrottledError | None = None
        for channel in (self._lookup_via_cdx, self._lookup_via_availability):
            try:
                return await channel(url)
            except ThrottledError as e:
                refusal = refusal or e
        raise refusal or ThrottledError()

    async def _get_json(self, endpoint: str, params: dict[str, str]):
        """Le JSON d'un canal. Leve ``ThrottledError`` s'il n'a pas repondu.

        Panne, timeout et reponse illisible sont regroupes a dessein : aucun ne
        dit « pas d'instantane ». Ils disent « pas de reponse », et c'est a
        l'appelant d'essayer ailleurs plutot que de conclure.
        """
        try:
            async with httpx.AsyncClient(timeout=self.LOOKUP_TIMEOUT) as client:
                response = await client.get(endpoint, params=params)
            refusal = self._refusal(response)
            if refusal is not None:
                raise refusal
            response.raise_for_status()
            return response.json()
        except ThrottledError:
            raise
        except Exception as e:  # noqa: BLE001 — l'autre canal a peut-etre mieux.
            # Le type, pas seulement le message : un `ReadTimeout` a un message
            # vide, et sans son nom le journal n'apprend rien a qui cherche.
            logger.info(
                "Wayback lookup unusable on %s for %s: %s %s",
                endpoint,
                params.get("url"),
                type(e).__name__,
                e,
            )
            raise ThrottledError() from e

    async def _lookup_via_cdx(self, url: str) -> tuple[str, str | None] | None:
        """L'index CDX. Leve ``ThrottledError`` faute de reponse exploitable."""
        params = {
            "url": url,
            "output": "json",
            "limit": "1",
            "filter": "statuscode:200",
            "fl": "timestamp,original",
        }
        rows = await self._get_json(self.CDX_URL, params)
        # CDX renvoie une matrice dont la premiere ligne est l'en-tete, et une
        # liste vide quand il n'a rien. Un HTML d'erreur en 200 n'est ni l'un
        # ni l'autre : on ne s'en sert pas pour conclure.
        if not isinstance(rows, list) or (rows and not isinstance(rows[0], list)):
            raise ThrottledError()
        if len(rows) < 2:
            return None
        timestamp, original = rows[1][0], rows[1][1]
        return f"https://web.archive.org/web/{timestamp}/{original}", timestamp

    async def _lookup_via_availability(self, url: str) -> tuple[str, str | None] | None:
        params = {"url": url}
        if self._api_key:
            params["api_key"] = self._api_key
        data = await self._get_json(self.AVAILABLE_URL, params)
        if not isinstance(data, dict):
            raise ThrottledError()

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
        """Archive un lot en deux temps, a une cadence que le service accepte.

        On sonde tout le lot d'abord, puis on ne demande une capture que pour
        ce qui en est reellement absent : une bibliographie academique cite
        surtout des travaux archives depuis des annees, et Save Page Now est
        la partie la plus lente et la plus limitee du service.

        Chaque URL est resolue avant d'etre sondee : c'est la ressource qu'il
        faut chercher et preserver, pas la redirection qui y mene.

        Ce qui depasse le budget reste `pending` -- la reprise paresseuse le
        reproposera au prochain affichage de la fiche, ce qui fournit aussi le
        delai dont Save Page Now a besoin pour produire ses captures.
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

        # D'abord regarder. Une bibliographie academique cite surtout des
        # travaux deja dans l'archive depuis des annees : leur demander une
        # capture, c'est payer la partie la plus lente et la plus limitee du
        # service pour un travail deja fait.
        pacer = _Pacer(self.LOOKUP_GAP, self.LOOKUP_CEILING, self.BATCH_BUDGET)
        absents: list[str] = []
        for source_id, url in todo:
            if pacer.exhausted:
                break
            # Viser la ressource, pas le panneau qui y mene. La latence du
            # sondage espace naturellement ces requetes, ce qui suffit : le
            # resolveur limite lui aussi les rafales (constate en mesurant).
            target = await self._resolve(url)
            # Consigner l'essai avant d'en connaitre l'issue : c'est ce qui
            # distingue une source traitee d'une source jamais atteinte, et
            # ce qui la fera passer en fin de file au prochain tour.
            await self._mark_attempted(source_id)
            found = await self._attempt(pacer, partial(self._lookup_snapshot, target))
            if found is None:
                results.append({"status": "pending", "reason": "no_snapshot_yet"})
                absents.append(target)
                continue
            results.append(await self._mark_archived(source_id, *found))

        # Puis demander une capture pour celles-la seulement. Save Page Now
        # travaille en differe : le prochain affichage de la fiche relancera le
        # sondage, et c'est lui qui les verra arriver.
        pacer = _Pacer(self.TRIGGER_GAP, self.TRIGGER_CEILING, self.BATCH_BUDGET)
        for url in absents:
            if pacer.exhausted:
                break
            await self._attempt(pacer, partial(self._trigger_save, url))

        return results

    async def _mark_attempted(self, source_id: UUID) -> None:
        """Date la tentative, sans rien conclure sur son issue.

        Avoir essaye n'est ni un succes ni un echec : seul `archive_status`
        repond a cette question, et il n'est pas touche ici.
        """
        result = await self._db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source:
            source.archive_attempted_at = datetime.now().replace(tzinfo=None)
            await self._db.commit()

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


def least_recently_attempted[S: _Attemptable](sources: list[S]) -> list[S]:
    """Les sources tentees le moins recemment d'abord, jamais tentees en tete.

    Un lot est borne par un budget de temps : il ne traite qu'un prefixe de la
    file. Servie toujours dans le meme ordre, la queue de cette file n'est pas
    traitee « plus tard » -- elle ne l'est **jamais**. Mesure en prod le
    2026-08-04 : 132 sources bloquees, dont certaines avaient une capture
    disponible a l'instant meme.

    Le tri est stable, donc deux sources equivalentes gardent leur ordre : rien
    ne justifierait de les brasser.
    """
    return sorted(sources, key=lambda s: s.archive_attempted_at or datetime.min)


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
