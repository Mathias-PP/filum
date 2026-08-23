"""Rejoint les deux 050 : la nature de fiche et le mode gratuit.

Les deux migrations sont parties du meme parent, sur deux branches mergees le
meme jour. Alembic s'est retrouve avec deux tetes, et `upgrade head` refuse de
choisir : le backend a redemarre en boucle sans jamais migrer.

Cette revision ne fait rien d'autre que rejoindre les deux branches. Elle est
vide parce qu'il n'y a rien a reconcilier : `050_card_kind` touche
`biblio_cards`, `050_mode_gratuit` touche les tables de l'agent, et aucune des
deux ne depend de l'autre.

Revision ID: 051_merge_050
Revises: 050_card_kind, 050_mode_gratuit
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "051_merge_050"
down_revision: str | tuple[str, ...] | None = ("050_card_kind", "050_mode_gratuit")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
