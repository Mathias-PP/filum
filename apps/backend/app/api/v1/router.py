from fastapi import APIRouter

from app.api.v1.endpoints import (
    attestations,
    auth,
    cards,
    excerpts,
    imports,
    og,
    sources,
    users,
    waitlist,
)

v1_router = APIRouter()

v1_router.include_router(attestations.router)
v1_router.include_router(auth.router)
v1_router.include_router(cards.router)
v1_router.include_router(excerpts.router)
v1_router.include_router(imports.router)
v1_router.include_router(og.router)
v1_router.include_router(sources.router)
v1_router.include_router(users.router)
v1_router.include_router(waitlist.router, tags=["waitlist"])


def create_router() -> APIRouter:
    return v1_router
