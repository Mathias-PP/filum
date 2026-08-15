"""Recherche d'extraits par le sens.

La similarite elle-meme ne se teste pas ici : les tests tournent sur SQLite,
qui n'a pas de type `vector`. Ce qui se teste sans Postgres, c'est ce qui
decide *avant* la requete -- la distinction entre indisponible et vide, la
qualification par le schema, le filtrage par le seuil et la forme du parametre
envoye au pilote.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import excerpt_search
from app.services.excerpt_search import (
    SIMILARITE_MINIMALE,
    litteral_vecteur,
    rechercher,
    requete_sql,
)


def test_litteral_vecteur_est_accepte_par_pgvector():
    # La forme textuelle entre crochets est celle que `CAST(... AS vector)`
    # convertit. Une liste Python partirait en tableau de reels, que Postgres
    # refuse de comparer a un vecteur.
    assert litteral_vecteur([0.5, -0.25]) == "[0.5,-0.25]"


def test_litteral_vecteur_vide():
    assert litteral_vecteur([]) == "[]"


def test_requete_sql_qualifie_operateur_et_type():
    sql = requete_sql("extensions")
    # Sans qualification, `<=>` et `vector` dependraient du search_path de la
    # session -- que rien ne garantit quand pgvector vit hors de `public`.
    assert "OPERATOR(extensions.<=>)" in sql
    assert "AS extensions.vector" in sql


def test_requete_sql_filtre_le_proprietaire_et_les_supprimes():
    sql = requete_sql("public")
    assert "c.user_id = :user_id" in sql
    assert "c.deleted_at IS NULL" in sql
    assert "s.deleted_at IS NULL" in sql


@pytest.mark.asyncio
async def test_requete_vide_ne_consomme_pas_d_embedding(monkeypatch):
    appels = []

    async def _embed(textes):
        appels.append(textes)
        return [[0.0]]

    monkeypatch.setattr(excerpt_search, "embed", _embed)
    assert await rechercher(None, uuid4(), "   ") == []
    assert appels == []


@pytest.mark.asyncio
async def test_service_absent_rend_none_et_non_liste_vide(monkeypatch):
    # Le coeur du contrat : une panne ne doit pas se lire comme « vos extraits
    # ne parlent pas de ca ».
    async def _embed(textes):
        return None

    monkeypatch.setattr(excerpt_search, "embed", _embed)
    assert await rechercher(None, uuid4(), "memoire de travail") is None


@pytest.mark.asyncio
async def test_pgvector_absent_rend_none(monkeypatch):
    async def _embed(textes):
        return [[0.1, 0.2]]

    async def _schema(db):
        return None

    monkeypatch.setattr(excerpt_search, "embed", _embed)
    monkeypatch.setattr(excerpt_search, "schema_du_type_vector", _schema)
    assert await rechercher(None, uuid4(), "memoire de travail") is None


class _LigneFactice:
    def __init__(self, similarite: float):
        self.excerpt_id = uuid4()
        self.text = "un passage"
        self.title = None
        self.context = None
        self.source_id = uuid4()
        self.source_title = "Un article"
        self.source_url = "https://example.org/a"
        self.card_id = uuid4()
        self.card_slug = "une-fiche"
        self.card_title = "Une fiche"
        self.similarite = similarite


class _DbFactice:
    def __init__(self, lignes):
        self.lignes = lignes
        self.parametres = None

    async def execute(self, requete, parametres=None):
        self.parametres = parametres
        return self.lignes


@pytest.mark.asyncio
async def test_le_seuil_ecarte_le_bruit_franc(monkeypatch):
    async def _embed(textes):
        return [[0.1, 0.2]]

    async def _schema(db):
        return "public"

    monkeypatch.setattr(excerpt_search, "embed", _embed)
    monkeypatch.setattr(excerpt_search, "schema_du_type_vector", _schema)

    db = _DbFactice([_LigneFactice(0.82), _LigneFactice(SIMILARITE_MINIMALE - 0.01)])
    resultats = await rechercher(db, uuid4(), "memoire de travail")

    assert resultats is not None
    assert [round(r.similarite, 2) for r in resultats] == [0.82]
    # Le vecteur part sous forme textuelle, jamais en liste Python.
    assert db.parametres["vecteur"] == "[0.1,0.2]"
