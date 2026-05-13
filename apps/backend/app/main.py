from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import create_router
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


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
    return {"status": "ok", "version": settings.app_version}


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


@app.get("/health/seed")
async def seed_health():
    """Diagnose: does the demo user + card exist?"""
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
