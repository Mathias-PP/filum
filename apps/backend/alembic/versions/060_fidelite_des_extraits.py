"""La source dit-elle ce que l'annotation lui fait dire.

Quatre colonnes sur `source_excerpts` et un interrupteur sur `users`.

`fidelity_verdict` est une enumeration fermee a six valeurs, stockee en chaine
plutot qu'en type Postgres : les six se discutent encore, et une migration de
type ENUM coute plus cher qu'une garde en Python (`fidelite.VERDICTS`).

`fidelity_scope` dit sur quoi le juge s'est prononce : `texte_integral`,
`resume_seul` ou `metadonnees_seules`. Sans lui, un verdict rendu sur un titre
se lirait comme un verdict rendu sur l'article.

Aucune colonne numerique, et c'est delibere. Un scalaire invite a la moyenne,
et une moyenne de jugements categoriels ne veut rien dire.

`NULL` sur `fidelity_verdict` se lit « jamais juge ». C'est un etat a afficher
tel quel, jamais comble par un defaut qui ferait passer l'extrait pour verifie.
Meme convention que `verified_at` juste au-dessus, dans le meme modele.

`users.fidelity_judge_enabled` vaut vrai par defaut. Le juge ne se declenche
pourtant que si le createur a configure une cle : rien ne depense l'argent de
quelqu'un qui n'a rien branche.

Revision ID: 060_fidelite_des_extraits
Revises: 059_source_retraction_reason
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "060_fidelite_des_extraits"
down_revision: str | None = "059_source_retraction_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_excerpts", sa.Column("fidelity_verdict", sa.String(24), nullable=True))
    op.add_column("source_excerpts", sa.Column("fidelity_scope", sa.String(24), nullable=True))
    op.add_column("source_excerpts", sa.Column("fidelity_checked_at", sa.DateTime(), nullable=True))
    op.add_column("source_excerpts", sa.Column("fidelity_note", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "fidelity_judge_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "fidelity_judge_enabled")
    op.drop_column("source_excerpts", "fidelity_note")
    op.drop_column("source_excerpts", "fidelity_checked_at")
    op.drop_column("source_excerpts", "fidelity_scope")
    op.drop_column("source_excerpts", "fidelity_verdict")
