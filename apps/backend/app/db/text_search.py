"""Comparer un motif tapé à la main au texte d'une colonne.

Le corpus est francophone et les titres portent des accents ; les motifs tapés
n'en portent souvent pas. Un agent qui a lu « Mémoire et cerveau » dans une
réponse translittérée redemandera « memoire ». Comparer les deux par simple
sous-chaîne fait répondre « rien » là où la fiche existe, ce qui se lit comme
un corpus vide plutôt que comme une recherche trop littérale.

Postgres sait replier les accents avec `unaccent()` (migration 037). SQLite,
sur lequel tournent les tests, ne le sait pas : le repli s'y réduit alors à
l'identité, et la comparaison reste celle d'avant. D'où la condition en deux
branches ci-dessous, qui n'enlève rien nulle part et ajoute là où c'est
possible.
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnOperators, FunctionElement
from sqlalchemy.types import String


class sans_accent(FunctionElement):  # noqa: N801  (nom de fonction SQL)
    """Le texte débarrassé de ses diacritiques, quand la base le sait faire."""

    type = String()
    name = "sans_accent"
    inherit_cache = True


@compiles(sans_accent)
def _sans_accent_defaut(element, compiler, **kw) -> str:
    # Sans `unaccent`, mieux vaut rendre la colonne telle quelle qu'échouer :
    # la recherche reste sensible aux accents, comme avant cette fonction.
    return str(compiler.process(list(element.clauses)[0], **kw))


@compiles(sans_accent, "postgresql")
def _sans_accent_postgres(element, compiler, **kw) -> str:
    return f"unaccent({compiler.process(list(element.clauses)[0], **kw)})"


def replier(texte: str) -> str:
    """Le motif débarrassé de ses diacritiques, côté Python.

    NFKD sépare la lettre de son accent, `Mn` désigne les marques combinantes.
    Le résultat sert de motif face à une colonne repliée par la base.
    """
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def contient(colonne: ColumnOperators, motif: str) -> ColumnElement[bool]:
    """La colonne contient le motif, aux accents près quand la base le permet.

    Deux branches en `OR` plutôt qu'une seule sur le texte replié : sur une
    base sans `unaccent`, replier le seul motif rendrait « mémoire »
    introuvable par « mémoire ». La branche littérale garantit qu'aucune
    recherche qui aboutissait n'aboutit plus.
    """
    terme = motif.strip().lower()
    litteral = func.lower(colonne).contains(terme, autoescape=True)
    replie = sans_accent(func.lower(colonne)).contains(replier(terme), autoescape=True)
    return or_(litteral, replie)
