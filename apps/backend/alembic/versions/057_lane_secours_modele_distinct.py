"""Mode gratuit : la lane de secours reprend un modele different du primaire.

La 052 posait `zai-alt` sur `glm-4.5-flash` pendant que `zai` tenait
`glm-4.7-flash`. Changer le modele primaire depuis l'administration ecrivait
alors la colonne `model` de `zai` sans regarder le secours : en production les
deux lanes ont fini sur `glm-4.5-flash`, meme endpoint, meme cle, meme modele.
La rotation existait toujours, mais le repli reproduisait exactement l'echec du
primaire, ce qui revient a ne pas avoir de repli.

Le code ecarte desormais les secours a chaque changement de primaire. Cette
migration repare les bases deja dans cet etat.

Revision ID: 057_lane_secours_modele_distinct
Revises: 056_workspace_provenance_seed
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "057_lane_secours_modele_distinct"
down_revision: str | None = "056_workspace_provenance_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Les deux seuls modeles gratuits Z.ai. Recopies plutot qu'importes de
#: `agent_gratuit.MODELES_GRATUITS` : une migration doit rester lisible telle
#: qu'elle a tourne, meme si le code evolue apres elle.
_MODELES = ("glm-4.7-flash", "glm-4.5-flash")


def upgrade() -> None:
    conn = op.get_bind()
    primaire = conn.execute(
        sa.text("SELECT model FROM agent_lanes WHERE slug = 'zai'")
    ).scalar_one_or_none()
    if primaire is None:
        return
    autre = next((m for m in _MODELES if m != primaire), None)
    if autre is None:
        return
    conn.execute(
        sa.text("UPDATE agent_lanes SET model = :autre WHERE slug LIKE 'zai-%' AND model = :meme"),
        {"autre": autre, "meme": primaire},
    )


def downgrade() -> None:
    # Rien a defaire : rendre aux deux lanes le meme modele retablirait le bug.
    pass
