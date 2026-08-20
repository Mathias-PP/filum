from fastapi import APIRouter

from app.api.v1.endpoints import (
    agent_providers,
    agent_workspace,
    attestations,
    auth,
    card_connections,
    cards,
    discover,
    excerpt_search,
    excerpts,
    feed,
    imports,
    oauth,
    og,
    sources,
    users,
)

v1_router = APIRouter()

v1_router.include_router(agent_providers.router)
v1_router.include_router(agent_workspace.router)
v1_router.include_router(attestations.router)
v1_router.include_router(auth.router)
v1_router.include_router(card_connections.router)
v1_router.include_router(cards.router)
v1_router.include_router(discover.router)
v1_router.include_router(excerpt_search.router)
v1_router.include_router(excerpts.router)
v1_router.include_router(feed.router)
v1_router.include_router(imports.router)
v1_router.include_router(oauth.router)
v1_router.include_router(og.router)
v1_router.include_router(sources.router)
v1_router.include_router(users.router)


def create_router() -> APIRouter:
    return v1_router
