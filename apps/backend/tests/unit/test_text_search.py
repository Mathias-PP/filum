"""« memoire » doit atteindre « Mémoire et cerveau ».

Le corpus est francophone, les motifs tapés le sont rarement. Un agent qui a
lu un titre translittéré le redemandera sans accents, et une recherche qui
répond « rien » se lit comme un corpus vide, pas comme une comparaison trop
littérale. C'est la même confusion qu'ailleurs dans le projet entre « rien
trouvé » et « pas pu chercher ».

Le repli se fait côté base, donc son rendu dépend du dialecte : ces tests
compilent la condition plutôt que de l'exécuter.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql, sqlite

from app.db.text_search import contient, replier
from app.models.biblio_card import BiblioCard


def _sql(dialecte) -> str:
    return str(
        contient(BiblioCard.title, "Mémoire").compile(
            dialect=dialecte, compile_kwargs={"literal_binds": True}
        )
    )


class TestRepliDuMotif:
    def test_les_diacritiques_tombent(self):
        assert replier("Mémoire et cerveau") == "Memoire et cerveau"
        assert replier("Où ça ? Français, ångström") == "Ou ca ? Francais, angstrom"

    def test_un_motif_sans_accent_ne_bouge_pas(self):
        assert replier("working memory") == "working memory"


class TestCompilation:
    def test_postgres_replie_la_colonne(self):
        sql = _sql(postgresql.dialect())
        assert "unaccent(" in sql
        # Le motif replie et le motif litteral sont tous deux cherches : sans
        # la branche litterale, une base sans `unaccent` perdrait les titres
        # accentues cherches avec leurs accents.
        assert "memoire" in sql.lower()
        assert "mémoire" in sql.lower()

    def test_sans_unaccent_la_condition_reste_valide(self):
        # SQLite n'a pas `unaccent`. La fonction s'y compile en identite : la
        # recherche redevient celle d'avant, elle n'echoue pas.
        sql = _sql(sqlite.dialect())
        assert "unaccent(" not in sql
        assert "lower(" in sql.lower()

    def test_les_jokers_sql_sont_echappes(self):
        # Sans echappement, chercher « % » ramene tout le corpus.
        sql = str(
            contient(BiblioCard.title, "100%").compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "ESCAPE" in sql.upper()
