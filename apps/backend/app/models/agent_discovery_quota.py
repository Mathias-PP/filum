from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AgentDiscoveryQuota(Base):
    __tablename__ = "agent_discovery_quota"
    __table_args__ = (
        UniqueConstraint("creator_id", "date", name="uq_discovery_quota_creator_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[str] = mapped_column(nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date(), nullable=False)
    messages_used: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
