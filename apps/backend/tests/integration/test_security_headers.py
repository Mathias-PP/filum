"""Contrat des headers HTTP renvoyes par l'API.

Ces assertions ne remplacent pas Caddy (qui pose CSP/HSTS en prod), mais elles
figent ce que FastAPI garantit lui-meme : CORS ecoute bien allow_origins, les
credentials passent (cookie de session), l'entete X-Request-ID est ajoute.

Cas historiques a proteger contre la regression :
- CORS mal configure = le browser rejette les reponses meme quand le backend
  repond 200 (bug vu en mai 2026, PR #33-#36).
- allow_credentials=False accidentel = plus d'auth cross-origin, deconnexion
  silencieuse de tous les users Vercel.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_expose_x_request_id(client):
    """Chaque reponse doit porter X-Request-ID : sans, tracer un incident dans
    les logs devient une chasse au trace timestamp par timestamp."""
    r = await client.get("/health")
    assert r.status_code == 200
    request_id = r.headers.get("X-Request-ID")
    assert request_id
    assert len(request_id) >= 4


@pytest.mark.asyncio
async def test_cors_repond_a_un_preflight_options(client):
    """Le browser envoie un OPTIONS preflight avant tout POST cross-origin.
    Sans reponse CORS complete, le fetch est droppe cote client meme si le
    backend aurait accepte la vraie requete."""
    r = await client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # 200 (preflight OK) ou 204. En cas de misconfig, on tombe en 400/405.
    assert r.status_code in (200, 204), f"preflight refuse : {r.status_code} {r.text[:200]}"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_autorise_les_credentials(client):
    """allow_credentials=True est le contrat sur lequel repose l'auth cookie
    cross-origin Vercel <-> backend. Le desactiver silencieusement
    deconnecterait tous les users du frontend prod."""
    r = await client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_refuse_une_origine_non_declaree(client):
    """Une origine inconnue ne doit pas obtenir de Access-Control-Allow-Origin :
    sinon n'importe quelle page tierce pourrait envoyer des credentials."""
    r = await client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://malveillant.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Le header ne doit pas etre echo. Starlette omet le header quand l'origine
    # n'est pas dans allow_origins.
    assert r.headers.get("access-control-allow-origin") != "https://malveillant.example"


@pytest.mark.asyncio
async def test_401_porte_toujours_les_headers_cors(client):
    """Bug historique (PR #33-#36 mai 2026) : quand un endpoint auth-protege
    renvoie 401 dans un contexte particulier, le browser voyait 'CORS error'
    trompeur au lieu de '401 unauthorized' parce que les headers CORS
    n'etaient pas emis sur la reponse d'erreur. Ce test fige le contrat."""
    r = await client.get("/api/v1/auth/me", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 401
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
