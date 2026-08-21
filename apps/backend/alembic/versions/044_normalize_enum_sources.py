"""Normalise les valeurs d'enum libres ecrites par les outils agent.

Revision ID: 044_normalize_enum_sources
Revises: 043_tool_call_id
Create Date: 2026-08-21

Les colonnes format/category/author_kind/stance de `sources` sont des VARCHAR
libres ; les outils MCP ecrivaient sans valider, et la fiche creatine
(2026-08-21) a rendu le defaut visible : une seule valeur hors vocabulaire fait
echouer TOUTE relecture (SourceResponse valide les enums a la sortie) — 500 sur
la vue publique, sources vides dans l'editeur, graphe en erreur.

Les tools valident desormais a l'entree (tools_write._valeur_enum). Cette
migration repare les lignes deja ecrites :

  Mappages cibles (synonymes clairs, meme sens que la valeur valide) :
    stance      'soutient'          -> 'appuie'
    author_kind 'institution'       -> 'institution-publique'
    category    'rapport-officiel'  -> 'article-scientifique'

  Filet de securite : toute autre valeur restee inconnue retombe sur l'etat
  neutre documente du modele (silence pour la stance, valeurs generiques pour
  les axes taxonomiques). Pre-MVP, un backfill best-effort est acceptable —
  precedent migration 007.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "044_normalize_enum_sources"
down_revision: str | None = "043_tool_call_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STANCES = ("appuie", "nuance-contredit", "mentionne", "contexte")
_CATEGORIES = (
    "article-scientifique",
    "preprint",
    "article-presse",
    "communique",
    "documentaire",
    "interview",
    "podcast",
    "blog",
    "post-social",
    "livre",
    "page-web",
    "notes",
)
_AUTEURS = (
    "chercheur",
    "media",
    "institution-publique",
    "gouvernement",
    "ecole",
    "laboratoire",
    "entreprise",
    "asso",
    "individu",
)
_FORMATS = ("texte", "video", "image", "audio", "data")


def _in(colonne: str, valeurs: tuple[str, ...]) -> str:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    return f"{colonne} NOT IN ({liste})"


def upgrade() -> None:
    # Synonymes : la valeur ecrite par l'agent veut dire la valeur valide.
    op.execute("UPDATE sources SET stance = 'appuie' WHERE stance = 'soutient'")
    op.execute(
        "UPDATE sources SET author_kind = 'institution-publique' WHERE author_kind = 'institution'"
    )
    op.execute(
        "UPDATE sources SET category = 'article-scientifique' WHERE category = 'rapport-officiel'"
    )

    # Filet : ce qui reste hors vocabulaire ne doit plus rendre aucune fiche
    # lisible. La stance inconnue redevient silence (NULL = non declare,
    # etat normal du modele) ; les axes taxonomiques prennent la valeur la
    # moins engageante.
    op.execute(f"UPDATE sources SET stance = NULL WHERE {_in('stance', _STANCES)}")
    op.execute(
        f"UPDATE sources SET category = 'page-web' WHERE {_in('category', _CATEGORIES)}"
    )
    op.execute(
        f"UPDATE sources SET author_kind = 'individu' WHERE {_in('author_kind', _AUTEURS)}"
    )
    op.execute(f"UPDATE sources SET format = 'texte' WHERE {_in('format', _FORMATS)}")


def downgrade() -> None:
    # Les mappings sont lossy (une valeur inconnue -> valeur neutre) : rien de
    # sensé a reconstruire. Le retour arriere ne sert qu'a la forme du schema,
    # inchangee ici.
    pass
