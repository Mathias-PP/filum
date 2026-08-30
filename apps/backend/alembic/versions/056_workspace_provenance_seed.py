"""Provenance d'un fichier de workspace : la version du modele dont il vient.

`seed()` n'inserait que les chemins absents et n'ecrasait jamais rien. C'est le
bon reflexe (personne ne veut perdre ses editions) mais pris seul il fige le
workspace a sa date de creation : mesure du 2026-08-30 en production, sur un
workspace reel, 10 fichiers a jour sur 27, 9 dans une version ancienne, et le
repertoire `agents/` entier jamais arrive.

Sans cette colonne, un fichier dont le contenu differe du modele pose une
question sans reponse : est-ce que la personne l'a edite, ou est-ce que le
modele a avance depuis ? Les deux cas demandent l'inverse l'un de l'autre.
`seed_sha256` garde l'empreinte de la version du modele dont le fichier est
issu, ce qui tranche : contenu inchange depuis le seed, on peut mettre a jour
sans rien perdre ; contenu modifie, on ne touche a rien.

NULL = provenance inconnue, et c'est l'etat de toutes les lignes existantes.
Volontairement pas de backfill : poser `seed_sha256 = sha256` reviendrait a
affirmer que personne n'a rien edite, et donnerait le droit d'ecraser des
editions reelles. Une provenance inconnue est traitee comme une divergence,
donc jamais ecrasee d'office.

Revision ID: 056_workspace_provenance_seed
Revises: 055_agent_session_objectif
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "056_workspace_provenance_seed"
down_revision: str | None = "055_agent_session_objectif"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace_files", sa.Column("seed_sha256", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_files", "seed_sha256")
