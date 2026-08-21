"""Mode decouverte : cle sponsorisee Philum pour essayer l'agent sans provider.

Quand `agent_discovery_enabled=True` dans la config ET que le createur n'a
aucun provider actif, l'endpoint chat utilise la cle serveur au lieu de
renvoyer une erreur. Un quota quotidien plafonne l'usage.

Recommandation prod : DeepSeek (API commerciale, ~0.27 $/M tokens, ToS sans
restriction sur l'usage multi-utilisateur sponsor) comme provider de decouverte.
Ne jamais utiliser Groq/Gemini free tier pour ca : leur ToS est "personal use".
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.agent_discovery_quota import AgentDiscoveryQuota
from app.models.agent_provider import AgentProvider
from app.schemas.agent_provider import PROVIDER_DEFAULT_BASE_URLS


class ErreurQuota(Exception):  # noqa: N818
    """Quota quotidien de decouverte epuise."""

    def __init__(self, remaining: int, quota: int) -> None:
        self.remaining = remaining
        self.quota = quota
        super().__init__(f"Quota decouverte epuise ({quota} messages/jour).")


def discovery_est_actif(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.agent_discovery_enabled and s.agent_discovery_api_key)


def _provider_base_url(provider_kind: str) -> str:
    return PROVIDER_DEFAULT_BASE_URLS.get(provider_kind, "")


def _chiffrer_cle_placeholder(api_key: str) -> str:
    """Chiffre la cle serveur pour construire un AgentProvider transient."""
    from app.core.config import get_settings as _gs
    from app.crypto.keygen import KeyManager

    km = KeyManager(_gs().master_encryption_key)
    return km.encrypt_private_key(api_key)


def resoudre_provider_decouverte(settings: Settings | None = None) -> AgentProvider:
    """Construit un AgentProvider transient portant la cle serveur.

    NE PAS inserer en base. Ce provider est cree a la volee, valable le temps
    d'un seul appel a boucle(). Il n'a pas de creator_id reel.
    """
    s = settings or get_settings()
    provider_kind = s.agent_discovery_provider or "deepseek"
    base_url = _provider_base_url(provider_kind)
    provider = AgentProvider()
    provider.id = uuid.uuid4()
    provider.creator_id = uuid.UUID(int=0)
    provider.provider = provider_kind
    provider.display_name = "Decouverte Philum"
    provider.base_url = base_url
    provider.model = s.agent_discovery_model or "deepseek-chat"
    provider.api_key_enc = _chiffrer_cle_placeholder(s.agent_discovery_api_key)
    provider.is_default = True
    return provider


def nom_public_provider(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    noms = {
        "deepseek": "DeepSeek",
        "groq": "Groq",
        "gemini": "Google Gemini",
        "mistral": "Mistral",
        "cerebras": "Cerebras",
        "openai": "OpenAI",
    }
    return noms.get(s.agent_discovery_provider or "deepseek", s.agent_discovery_provider or "IA")


async def verifier_quota(
    db: AsyncSession, creator_id: Any, settings: Settings | None = None
) -> int:
    """Verifie le quota du jour. Leve ErreurQuota si depasse. Rend le restant."""
    s = settings or get_settings()
    quota = s.agent_discovery_daily_quota_messages
    today = date.today()
    result = await db.execute(
        select(AgentDiscoveryQuota).where(
            AgentDiscoveryQuota.creator_id == str(creator_id),
            AgentDiscoveryQuota.date == today,
        )
    )
    row = result.scalar_one_or_none()
    used = row.messages_used if row else 0
    remaining = max(0, quota - used)
    if remaining <= 0:
        raise ErreurQuota(remaining=0, quota=quota)
    return remaining


async def consommer_message(
    db: AsyncSession, creator_id: Any, settings: Settings | None = None
) -> None:
    """Increment atomique du compteur quotidien.

    SELECT + UPDATE/INSERT sequentiel : compatible SQLite (tests) et Postgres
    (prod). Pas de vrai atomique cross-process, mais le quota est indicatif
    (les sessions paralleles sont rares en decouverte).
    """
    today = date.today()
    creator_str = str(creator_id)
    result = await db.execute(
        select(AgentDiscoveryQuota).where(
            AgentDiscoveryQuota.creator_id == creator_str,
            AgentDiscoveryQuota.date == today,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(
            AgentDiscoveryQuota(
                id=uuid.uuid4(),
                creator_id=creator_str,
                date=today,
                messages_used=1,
            )
        )
    else:
        await db.execute(
            update(AgentDiscoveryQuota)
            .where(AgentDiscoveryQuota.id == row.id)
            .values(messages_used=row.messages_used + 1)
        )
    await db.commit()
