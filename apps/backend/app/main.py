from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import create_router
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"CORS allowed origins: {settings.cors_origins!r}")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "[%s] %s %s → %s (%dms)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(create_router(), prefix=settings.api_v1_prefix)


@app.get("/health")
async def health_check():
    import os

    return {
        "status": "ok",
        "version": settings.app_version,
        # Railway sets RAILWAY_GIT_COMMIT_SHA on every deploy; falls back to
        # local env vars if running outside Railway. Useful to verify which
        # commit is actually live in prod.
        "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT_SHA")
        or "unknown",
    }


@app.get("/health/database")
async def database_health():
    from sqlalchemy import text

    from app.db.database import async_session_maker

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


@app.get("/health/publish-diagnose")
async def publish_diagnose():
    """Exercise the publish code path on the demo user's seeded card.

    Debug-only: returns tracebacks and internal paths, so it must not be
    reachable on a production deployment (debug=false). Dry-run: the UPDATE
    is flushed (exercising the exact DB write path) then rolled back.
    """
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    import traceback
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.database import async_session_maker
    from app.models.biblio_card import BiblioCard, CardStatus
    from app.models.source import Source

    trace: list[str] = []
    try:
        async with async_session_maker() as db:
            trace.append("session_opened")
            result = await db.execute(
                select(BiblioCard)
                .where(BiblioCard.deleted_at.is_(None))
                .options(selectinload(BiblioCard.sources).selectinload(Source.excerpts))
                .options(selectinload(BiblioCard.user))
                .limit(1)
            )
            card = result.scalar_one_or_none()
            if not card:
                return {"ok": False, "trace": trace, "reason": "no_card_in_db"}
            trace.append(f"card_loaded id={card.id} sources={len(card.sources)}")
            if not card.sources:
                return {"ok": False, "trace": trace, "reason": "card_has_no_sources"}
            if not card.user:
                return {"ok": False, "trace": trace, "reason": "card_has_no_user"}
            trace.append(f"user_loaded username={card.user.username}")
            # Mirror CardService.publish_card WITHOUT its commit: flush emits
            # the same UPDATE (naive datetime, enum coercion) but stays inside
            # the transaction, and the rollback below reverts it. The previous
            # version called publish_card(), whose internal commit made the
            # "rollback" a no-op — every diagnose hit silently published a card.
            username = card.user.username
            card_slug = card.slug
            card.published_at = datetime.now(UTC).replace(tzinfo=None)
            card.status = CardStatus.PUBLISHED
            trace.append("flushing_publish_update")
            await db.flush()
            trace.append("flush_ok")
            await db.rollback()
            trace.append("rolled_back")
            return {
                "ok": True,
                "trace": trace,
                "public_url": f"{settings.frontend_base_url}/@{username}/{card_slug}",
            }
    except Exception as exc:
        return {
            "ok": False,
            "trace": trace,
            "error_type": type(exc).__name__,
            "error_msg": str(exc),
            "traceback": traceback.format_exc().splitlines()[-15:],
        }


@app.get("/health/seed")
async def seed_health():
    """Diagnose: does the demo user + card exist? Debug-only.

    Enumerates every username and card slug, so it must not be reachable
    on a production deployment (debug=false).
    """
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    from sqlalchemy import select

    from app.db.database import async_session_maker
    from app.models.biblio_card import BiblioCard
    from app.models.user import User

    async with async_session_maker() as session:
        users = (await session.execute(select(User.username, User.id))).all()
        cards = (
            await session.execute(select(BiblioCard.slug, BiblioCard.status, BiblioCard.user_id))
        ).all()
        return {
            "users": [{"username": u.username, "id": str(u.id)} for u in users],
            "cards": [
                {"slug": c.slug, "status": c.status, "user_id": str(c.user_id)} for c in cards
            ],
        }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "; ".join(messages),
                "details": errors,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.detail.get("code", "error")
                if isinstance(exc.detail, dict)
                else "error",
                "message": exc.detail.get("message", str(exc.detail))
                if isinstance(exc.detail, dict)
                else str(exc.detail),
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred",
            }
        },
    )
