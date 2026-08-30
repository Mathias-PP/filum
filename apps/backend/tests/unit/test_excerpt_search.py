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
        self.verified_status = "found"
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


def _resultat(trouve_par: str, similarite: float = 0.0) -> excerpt_search.Resultat:
    return excerpt_search.Resultat(
        excerpt_id=uuid4(),
        text="un passage",
        title=None,
        context=None,
        source_id=uuid4(),
        source_title=None,
        source_url="https://example.org/a",
        card_id=uuid4(),
        card_slug="une-fiche",
        card_title="Une fiche",
        verified_status=None,
        similarite=similarite,
        trouve_par=frozenset({trouve_par}),
    )


@pytest.mark.asyncio
async def test_la_fusion_nomme_les_deux_jambes(monkeypatch):
    commun = _resultat("sens", 0.71)
    seul_par_les_mots = _resultat("mots")

    async def _sens(db, user_id, requete, limite=20):
        return [commun]

    async def _mots(db, user_id, requete, limite=20):
        return [seul_par_les_mots, commun]

    monkeypatch.setattr(excerpt_search, "rechercher", _sens)
    monkeypatch.setattr(excerpt_search, "rechercher_par_mots", _mots)

    resultats = await excerpt_search.rechercher_fusionne(None, uuid4(), "sommeil")
    par_id = {r.excerpt_id: r.trouve_par for r in resultats}

    assert par_id[commun.excerpt_id] == frozenset({"sens", "mots"})
    assert par_id[seul_par_les_mots.excerpt_id] == frozenset({"mots"})
    # L'accord des deux jambes passe devant le premier d'une seule.
    assert resultats[0].excerpt_id == commun.excerpt_id
    # Et c'est la version semantique qui est rendue : elle seule sait la mesure.
    assert resultats[0].similarite == 0.71


@pytest.mark.asyncio
async def test_la_fusion_survit_a_l_absence_de_la_jambe_semantique(monkeypatch):
    """Sans service d'embeddings, la recherche par les mots repond seule.

    `rechercher` rend `None` et non une liste vide : la fusion doit lire ce
    `None` comme « cette jambe n'a pas eu lieu », pas comme « elle n'a rien
    trouve », faute de quoi une panne effacerait aussi les resultats lexicaux.
    """
    par_mots = [_resultat("mots"), _resultat("mots")]

    async def _sens(db, user_id, requete, limite=20):
        return None

    async def _mots(db, user_id, requete, limite=20):
        return par_mots

    monkeypatch.setattr(excerpt_search, "rechercher", _sens)
    monkeypatch.setattr(excerpt_search, "rechercher_par_mots", _mots)

    resultats = await excerpt_search.rechercher_fusionne(None, uuid4(), "sommeil")

    assert [r.excerpt_id for r in resultats] == [r.excerpt_id for r in par_mots]
    assert all(r.trouve_par == frozenset({"mots"}) for r in resultats)
