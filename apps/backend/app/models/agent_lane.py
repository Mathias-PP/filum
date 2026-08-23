from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AgentLane(Base):
    """Une lane du mode gratuit : un couple (fournisseur, modele) serveur.

    La cle API ne vit JAMAIS en base : elle est resolue a la volee depuis les
    settings (``agent_gratuit_<slug>_api_key``). Une lane sans cle configuree
    est simplement ignoree par le routeur.
    """

    __tablename__ = "agent_lanes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Identifiant stable utilise pour retrouver la cle en settings.
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    # Nom affiche a l'utilisateur dans la banniere (« GLM · Z.ai »).
    label_public: Mapped[str] = mapped_column(String(80), nullable=False)
    # Protocole du client LLM. « custom » = OpenAI-compatible avec base_url.
    provider_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="custom")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    rpm_cap: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    rpd_cap: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)


class AgentLaneUsage(Base):
    """Compteur quotidien + cooldown d'une lane.

    ``cooldown_until`` est pose quand la lane renvoie un 429 : le routeur
    l'ecarte pendant la fenetre au lieu de marteler un endpoint qui refuse.
    """

    __tablename__ = "agent_lane_usage"
    __table_args__ = (UniqueConstraint("lane_id", "date", name="uq_agent_lane_usage_lane_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lane_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date(), nullable=False)
    requests_used: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class AgentGratuitConsent(Base):
    """Consentement explicite de l'utilisateur au mode gratuit.

    Une ligne par createur (PK = creator_id) : reconsentir ecrase la version
    precedente. Le texte du warning est versionne cote service ; une montée
    de version force un nouveau consentement.
    """

    __tablename__ = "agent_gratuit_consents"

    creator_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
