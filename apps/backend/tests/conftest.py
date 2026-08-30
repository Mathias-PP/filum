from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["database_url"] = "sqlite+aiosqlite:///./test.db"
os.environ["session_secret"] = "test-secret-for-ci-session-32chars"
os.environ["master_encryption_key"] = "test-key-for-ci-encryption-32b"
os.environ["google_client_id"] = "test-client-id.apps.googleusercontent.com"
os.environ["google_client_secret"] = "test-client-secret"
os.environ["google_redirect_uri"] = "http://test/api/v1/auth/google/callback"
os.environ["ci"] = "true"

# Windows stocke les variables d'environnement en majuscules quoi qu'on ecrive :
# les affectations ci-dessus deviennent DATABASE_URL, SESSION_SECRET, etc. Avec
# `case_sensitive=True` (ADR-010), pydantic-settings ne les voit alors pas et
# retombe sur les defauts -- dont un Postgres local absent. Les tests adossés a
# la base echouaient donc systematiquement sur un poste Windows, et seule la CI
# Linux les executait vraiment.
#
# On relache la contrainte ici et nulle part ailleurs : la garder en production
# evite qu'un `DEBUG=1` d'un outil tiers active le mode debug par accident.
from app.core.config import Settings, get_settings  # noqa: E402

Settings.model_config["case_sensitive"] = False
get_settings.cache_clear()

import app.models.agent_discovery_quota  # noqa: E402, F401
import app.models.agent_lane  # noqa: E402, F401
import app.models.agent_provider  # noqa: E402, F401
import app.models.agent_session  # noqa: E402, F401
import app.models.audit_event  # noqa: E402, F401
import app.models.biblio_card  # noqa: E402, F401
import app.models.claim_request  # noqa: E402, F401
import app.models.content_attestation  # noqa: E402, F401
import app.models.excerpt_embedding  # noqa: E402, F401
import app.models.feed_event  # noqa: E402, F401
import app.models.linked_account  # noqa: E402, F401
import app.models.oauth  # noqa: E402, F401
import app.models.source  # noqa: E402, F401
import app.models.source_excerpt  # noqa: E402, F401
import app.models.user  # noqa: E402, F401
import app.models.workspace_file  # noqa: E402, F401
from app.db.database import Base, engine  # noqa: E402


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(bind=engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_app():
    from app.main import app

    yield app


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_service(db_session):
    from app.services.auth import AuthService

    return AuthService(db_session)


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.models.user import User

    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        display_name="Test User",
        public_key="t" * 64,
        encrypted_private_key="encrypted_test_key",
        google_id="google_test_123",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest_asyncio.fixture
async def session_token(auth_service, test_user) -> str:
    return auth_service.create_session(test_user.id)


@pytest.fixture(autouse=True)
def _relais_de_lecture_hors_ligne(monkeypatch):
    """Coupe le relais de lecture pour toute la suite.

    Contrairement aux autres etages de la cascade, celui-ci est actif par
    defaut (son point d'entree ne demande pas de cle). Sans cette coupure, tout
    test qui atteint `_texte_de_la_source` sans avoir neutralise le reseau
    partirait chez un tiers : lent, dependant d'un quota, et vert ou rouge
    selon la meteo. Les tests du relais lui-meme rebranchent le reglage.
    """
    from app.extractors import lecteur_relais

    monkeypatch.setattr(lecteur_relais.settings, "lecture_relais_endpoint", "")


@pytest.fixture(autouse=True)
def _existence_des_sources_admise(monkeypatch):
    """Admet l'existence des adresses citees par les tests, sans reseau.

    `add_source` joint l'adresse avant d'ecrire, ce qui est le point de la
    garde. Les fixtures de la suite citent des URLs de convention qui n'existent
    pas : sans cette neutralisation, chaque test paierait un aller-retour reseau
    pour se voir refuser. Les tests de la garde elle-meme rebranchent la
    fonction sur un double qui refuse.
    """
    from app.mcp_server import tools_write

    async def _admettre(url: str | None, doi: str | None) -> None:
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", _admettre)
