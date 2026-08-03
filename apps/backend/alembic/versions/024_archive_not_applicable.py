"""Les sources sans URL ne sont pas des echecs d'archivage.

Constate en prod (aout 2026) : 4 des 152 sources d'une fiche etaient inscrites
`failed` parce qu'elles n'ont pas d'URL -- un manuel DSM-IV-TR, un chapitre de
livre, extraits d'un depot editeur qui ne fournissait qu'un titre. `failed`
affirme qu'on a essaye et que la page est perdue : c'est faux, et cela
condamnait l'encart « Archivees » a afficher 148/152 a perpetuite.

`archive_status` est une colonne texte (String(20)), pas un type enum
Postgres : la nouvelle valeur ne demande aucun changement de schema.

Revision ID: 024_archive_na
Revises: 023_reset_archives
"""

from __future__ import annotations

from alembic import op

revision: str = "024_archive_na"
down_revision: str | None = "023_reset_archives"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sources
           SET archive_status = 'not_applicable'
         WHERE archive_status IN ('failed', 'pending')
           AND (url IS NULL OR btrim(url) = '')
        """
    )


def downgrade() -> None:
    # Retour a l'etat anterieur : ces lignes etaient `failed`. Le downgrade
    # les y ramene pour que le schema reste coherent avec le code d'avant,
    # meme si l'information qu'il retablit est fausse.
    op.execute(
        """
        UPDATE sources
           SET archive_status = 'failed'
         WHERE archive_status = 'not_applicable'
        """
    )
