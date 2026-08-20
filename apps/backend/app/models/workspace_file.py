from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class WorkspaceFile(Base):
    """Un fichier du workspace de configuration ICM d'un créateur.

    Filesystem logique persisté en base : chaque créateur hérite d'une copie du
    template ICM (`app/agent_workspace_seed/`) qu'il peut éditer via l'API (et
    bientôt l'agent). Le chemin est normalisé (relatif, racines fermées) et le
    `sha256` traçe le contenu pour l'audit.
    """

    __tablename__ = "workspace_files"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=None,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(default=None, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("creator_id", "path", name="uq_workspace_files_creator_path"),
    )

    def __repr__(self) -> str:
        return f"<WorkspaceFile {self.path} creator={self.creator_id}>"
