"""Mode gratuit : lane de secours pour la rotation automatique.

Deuxieme lane Z.ai sur un modele different du primaire : quand le primaire
repond 429/surcharge (le tier gratuit glm-4.7-flash sature aux heures de
pointe), le routeur existant pose un cooldown et les tours suivants partent
sur le secours — sans intervention manuelle.

La cle vient des memes settings que le primaire (`cle_lane` resout tout slug
`zai*`) ; seule la colonne `model` distingue les deux lanes.

Revision ID: 052_lane_zai_secours
Revises: 051_mode_gratuit
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "052_lane_zai_secours"
down_revision: str | None = "051_mode_gratuit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = sa.table(
    "agent_lanes",
    sa.column("id", sa.Uuid()),
    sa.column("slug", sa.String),
    sa.column("label_public", sa.String),
    sa.column("provider_kind", sa.String),
    sa.column("base_url", sa.String),
    sa.column("model", sa.String),
    sa.column("rpm_cap", sa.Integer),
    sa.column("rpd_cap", sa.Integer),
    sa.column("actif", sa.Boolean),
    sa.column("position", sa.Integer),
)


def upgrade() -> None:
    conn = op.get_bind()
    existe = conn.execute(sa.text("SELECT 1 FROM agent_lanes WHERE slug = 'zai-alt'")).scalar()
    if existe:
        return
    # Idempotent : un deploiement rejoue ne doit pas dupliquer la lane.
    # `bulk_insert` et pas un INSERT en texte, comme en 051 : PostgreSQL
    # refuse une chaine dans une colonne `uuid`, la ou SQLite l'accepte.
    op.bulk_insert(
        _TABLE,
        [
            {
                "id": uuid.uuid4(),
                "slug": "zai-alt",
                "label_public": "GLM · Z.ai (secours)",
                "provider_kind": "custom",
                "base_url": "https://api.z.ai/api/paas/v4",
                "model": "glm-4.5-flash",
                "rpm_cap": 3,
                "rpd_cap": 900,
                "actif": True,
                "position": 10,
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM agent_lanes WHERE slug = 'zai-alt'"))
