"""Rate limit sur endpoints REST publics — sanity check du dispositif.

Seul le MCP avait un test 429 dedie (`test_mcp_mount.py`). Un changement de
config slowapi qui desarme le rate-limit REST passerait aujourd'hui la CI sans
alerte. Ce fichier cible /sources/extract (10/minute, non-authentifie, expose
au SSRF, cf. `assert_url_is_safe`) : le decorateur limiter s'evalue avant la
fonction de vue et court-circuite tout, meme sur une URL invalide.

On ne teste pas chaque endpoint limite : la question est « le mecanisme
fonctionne-t-il ? », pas « chaque decorateur est-il pose ? ». Un seul point
d'observation prouve que la piece est branchee.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # slowapi conserve un compteur global entre les tests : le remettre a zero
    # pour que ce test ne depende pas de l'ordre d'execution ni des autres.
    limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    limiter.reset()


@pytest.mark.asyncio
async def test_sources_extract_declenche_429_apres_dix_appels(client):
    """/sources/extract est limite a 10/minute. Le 11e appel doit rendre 429.

    L'URL importe peu (l'ASGI n'atteint pas le reseau ici) ; le decorateur
    slowapi mesure les hits par IP avant meme d'entrer dans la vue.
    """
    for i in range(10):
        r = await client.get("/api/v1/sources/extract?url=https://example.org/a")
        assert r.status_code != 429, f"429 premature au tour {i + 1} : {r.text[:200]}"

    over = await client.get("/api/v1/sources/extract?url=https://example.org/a")
    assert over.status_code == 429, over.text


@pytest.mark.asyncio
async def test_le_rate_limit_ne_deborde_pas_sur_les_autres_endpoints(client):
    """La limite est par (IP, route). /health reste servi pendant que
    /sources/extract est bloque. Sans ca, une seule route saturee mettrait
    l'application entiere hors service pour un client donne."""
    # Sature /sources/extract.
    for _ in range(11):
        await client.get("/api/v1/sources/extract?url=https://example.org/a")

    # /health doit repondre normalement.
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
