"""Mode gratuit : rotation de lanes serveur sans clé côté utilisateur.

Différence fondamentale avec le mode découverte (``agent_discovery``) :
ici l'utilisateur doit **consentir explicitement** — les fournisseurs
gratuits (Z.ai tier gratuit aujourd'hui) se réservent le droit de conserver
les échanges et de les utiliser pour entraîner leurs modèles. Le consentement
est versionné : si le texte du warning change, il faut reconsentir.

Le routeur choisit la première lane disponible dans l'ordre de ``position``
en écartant celles dont le quota journalier est épuisé ou qui sont en
cooldown (429 récent). Les clés vivent exclusivement dans les settings ;
une lane sans clé configurée est invisible.

Réutilise ``AgentDiscoveryQuota`` comme compteur quotidien par utilisateur :
même forme (creator_id + date), même sémantique « budget plateforme » —
le mode gratuit a simplement son propre plafond dans les settings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.agent_discovery_quota import AgentDiscoveryQuota
from app.models.agent_lane import AgentGratuitConsent, AgentLane, AgentLaneUsage
from app.models.agent_provider import AgentProvider

#: Version du texte du warning. Incrementer a chaque changement de fond :
#: un utilisateur qui a consenti a v1 ne couvre pas v2.
VERSION_WARNING = "2026-08-23-v1"

#: Duree du cooldown pose quand une lane renvoie un 429.
COOLDOWN_MINUTES = 10


def _maintenant() -> datetime:
    """L'instant courant en UTC, sans fuseau attache.

    Les colonnes de ce module sont des `TIMESTAMP WITHOUT TIME ZONE`. Postgres
    refuse un datetime « aware » sur une telle colonne (`can't subtract
    offset-naive and offset-aware datetimes`), la ou SQLite l'accepte : le
    defaut ne se voit qu'en production, jamais dans les tests.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class ErreurQuotaGratuit(Exception):  # noqa: N818
    """Quota quotidien gratuit de l'utilisateur epuise."""

    def __init__(self, quota: int) -> None:
        self.quota = quota
        super().__init__(f"Quota gratuit epuise ({quota} messages/jour).")


class LaneActive(NamedTuple):
    """Une lane retenue par le routeur, prete a servir un tour."""

    lane: AgentLane
    provider: AgentProvider  # transient, jamais insere en base


def cle_lane(slug: str, settings: Settings | None = None) -> str:
    """Cle API d'une lane depuis les settings (jamais en base)."""
    s = settings or get_settings()
    return {"zai": s.agent_gratuit_zai_api_key}.get(slug, "")


def mode_disponible(settings: Settings | None = None) -> bool:
    """Le mode existe-t-il sur cette instance ? (active ET au moins une cle)"""
    s = settings or get_settings()
    return bool(s.agent_gratuit_enabled and cle_lane("zai", s))


def _chiffrer_cle(api_key: str) -> str:
    from app.crypto.keygen import KeyManager

    return KeyManager(get_settings().master_encryption_key).encrypt_private_key(api_key)


def _provider_transient(lane: AgentLane, settings: Settings | None = None) -> AgentProvider:
    """Construit le provider ephemere qui porte la cle serveur.

    NE PAS inserer en base : valable le temps d'un appel a ``boucle``,
    exactement comme ``resoudre_provider_decouverte``.
    """
    s = settings or get_settings()
    provider = AgentProvider()
    provider.id = uuid.uuid4()
    provider.creator_id = uuid.UUID(int=0)
    provider.provider = lane.provider_kind
    provider.display_name = f"Gratuit · {lane.label_public}"
    provider.base_url = lane.base_url
    provider.model = lane.model
    provider.api_key_enc = _chiffrer_cle(cle_lane(lane.slug, s))
    provider.is_default = True
    return provider


# ---------------------------------------------------------------------------
# Consentement
# ---------------------------------------------------------------------------


async def etat_consentement(
    db: AsyncSession, creator_id: uuid.UUID, settings: Settings | None = None
) -> dict:
    """Etat expose a l'UI : disponible sur l'instance ? active pour cet utilisateur ?"""
    s = settings or get_settings()
    row = await db.get(AgentGratuitConsent, str(creator_id))
    actif = bool(row and row.version == VERSION_WARNING)
    # Le nom du fournisseur qui servirait le prochain tour : l'UI l'affiche a
    # la place de la cle et du modele pour ne pas suggerer qu'ils comptent.
    fournisseur = None
    if actif:
        lane_active = await choisir_lane(db, s)
        if lane_active is not None:
            fournisseur = lane_active.lane.label_public
    return {
        "disponible": mode_disponible(s),
        "actif": actif,
        "version_warning": VERSION_WARNING,
        "fournisseur_actuel": fournisseur,
    }


async def est_consentant(db: AsyncSession, creator_id: uuid.UUID) -> bool:
    row = await db.get(AgentGratuitConsent, str(creator_id))
    return bool(row and row.version == VERSION_WARNING)


async def donner_consentement(db: AsyncSession, creator_id: uuid.UUID, version: str) -> None:
    """Enregistre le consentement. Refuse une version inconnue (texte perime)."""
    if version != VERSION_WARNING:
        raise ValueError("version_warning_inconnue")
    await db.merge(
        AgentGratuitConsent(
            creator_id=str(creator_id),
            version=version,
            consent_at=_maintenant(),
        )
    )
    await db.commit()


async def retirer_consentement(db: AsyncSession, creator_id: uuid.UUID) -> None:
    row = await db.get(AgentGratuitConsent, str(creator_id))
    if row is not None:
        await db.delete(row)
        await db.commit()


# ---------------------------------------------------------------------------
# Routeur de lanes
# ---------------------------------------------------------------------------


async def choisir_lane(db: AsyncSession, settings: Settings | None = None) -> LaneActive | None:
    """Premiere lane utilisable : active, avec cle, hors quota et hors cooldown."""
    s = settings or get_settings()
    result = await db.execute(
        select(AgentLane).where(AgentLane.actif.is_(True)).order_by(AgentLane.position.asc())
    )
    today = date.today()
    now = _maintenant()
    for lane in result.scalars():
        if not cle_lane(lane.slug, s):
            continue
        usage = (
            await db.execute(
                select(AgentLaneUsage).where(
                    AgentLaneUsage.lane_id == lane.id,
                    AgentLaneUsage.date == today,
                )
            )
        ).scalar_one_or_none()
        if usage is not None:
            if usage.cooldown_until is not None and usage.cooldown_until > now:
                continue
            if lane.rpd_cap is not None and usage.requests_used >= lane.rpd_cap:
                continue
        return LaneActive(lane=lane, provider=_provider_transient(lane, s))
    return None


async def consommer_requete(db: AsyncSession, lane: AgentLane) -> None:
    """+1 requete sur la lane du jour. SELECT puis INSERT/UPDATE sequentiels :
    compatible SQLite (tests) et Postgres (prod), quota indicatif."""
    today = date.today()
    usage = (
        await db.execute(
            select(AgentLaneUsage).where(
                AgentLaneUsage.lane_id == lane.id,
                AgentLaneUsage.date == today,
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        db.add(AgentLaneUsage(id=uuid.uuid4(), lane_id=lane.id, date=today, requests_used=1))
    else:
        await db.execute(
            update(AgentLaneUsage)
            .where(AgentLaneUsage.id == usage.id)
            .values(requests_used=usage.requests_used + 1)
        )
    await db.commit()


async def signaler_echec(
    db: AsyncSession, lane: AgentLane, minutes: int = COOLDOWN_MINUTES
) -> None:
    """Pose un cooldown sur la lane (rate limit, erreur fournisseur).

    Le routeur l'ecartera automatiquement pendant la fenetre ; les autres
    lanes prendront le relais sans intervention.
    """
    echeance = _maintenant() + timedelta(minutes=minutes)
    today = date.today()
    usage = (
        await db.execute(
            select(AgentLaneUsage).where(
                AgentLaneUsage.lane_id == lane.id,
                AgentLaneUsage.date == today,
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        db.add(
            AgentLaneUsage(id=uuid.uuid4(), lane_id=lane.id, date=today, cooldown_until=echeance)
        )
    else:
        await db.execute(
            update(AgentLaneUsage)
            .where(AgentLaneUsage.id == usage.id)
            .values(cooldown_until=echeance)
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Quota quotidien par utilisateur (compteur plateforme partage)
# ---------------------------------------------------------------------------


async def verifier_quota_utilisateur(
    db: AsyncSession, creator_id: uuid.UUID, settings: Settings | None = None
) -> int:
    """Rend le nombre de messages restants aujourd'hui. Leve ErreurQuotaGratuit."""
    s = settings or get_settings()
    quota = s.agent_gratuit_daily_quota_messages
    row = (
        await db.execute(
            select(AgentDiscoveryQuota).where(
                AgentDiscoveryQuota.creator_id == str(creator_id),
                AgentDiscoveryQuota.date == date.today(),
            )
        )
    ).scalar_one_or_none()
    used = row.messages_used if row else 0
    remaining = max(0, quota - used)
    if remaining <= 0:
        raise ErreurQuotaGratuit(quota)
    return remaining


async def consommer_message_utilisateur(db: AsyncSession, creator_id: uuid.UUID) -> None:
    """Incrément atomique du compteur quotidien utilisateur."""
    today = date.today()
    creator_str = str(creator_id)
    row = (
        await db.execute(
            select(AgentDiscoveryQuota).where(
                AgentDiscoveryQuota.creator_id == creator_str,
                AgentDiscoveryQuota.date == today,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            AgentDiscoveryQuota(
                id=uuid.uuid4(), creator_id=creator_str, date=today, messages_used=1
            )
        )
    else:
        await db.execute(
            update(AgentDiscoveryQuota)
            .where(AgentDiscoveryQuota.id == row.id)
            .values(messages_used=row.messages_used + 1)
        )
    await db.commit()
