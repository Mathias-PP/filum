from fastapi import APIRouter

from app.api.v1.endpoints import auth, cards, sources, users

v1_router = APIRouter()

v1_router.include_router(auth.router)
v1_router.include_router(cards.router)
v1_router.include_router(sources.router)
v1_router.include_router(users.router)


def create_router() -> APIRouter:
    return v1_router
