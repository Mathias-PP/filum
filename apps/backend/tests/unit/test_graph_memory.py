"""Le rappel du graphe : ce qu'il amorce, ce qu'il nomme, ce qu'il refuse.

Le module n'avait aucun test. Les quatre défauts corrigés ici (nœud de fiche
dédoublé, amorçage par sous-chaîne, en-tête inventé, reconstruction sans
garde) étaient tous invisibles à l'exécution : le rappel rendait un résultat
plausible, simplement pas celui de la question posée.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.sql import Select

from app.models.biblio_card import BiblioCard
from app.models.graph_memory import GraphAlias, GraphEntity, GraphRelation
from app.models.source import Source
from app.services import graph_memory
from app.services.graph_memory import (
    Facts,
    ReconstructionTropRecenteError,
    _mot_entier,
    build_graph,
    entity_id,
    mots_utiles,
)


class _Scalars:
    def __init__(self, objets):
        self._objets = objets

    def scalars(self):
        return self

    def all(self):
        return self._objets


class _FauxSession:
    """Le strict nécessaire pour dérouler `build_graph` hors base."""

    def __init__(self, cards, sources):
        self._resultats = [_Scalars(cards), _Scalars(sources)]
        self.ajouts: list = []
        self.commits = 0

    async def execute(self, requete, params=None):
        if isinstance(requete, Select) and self._resultats:
            return self._resultats.pop(0)
        return _Scalars([])

    def add(self, objet):
        self.ajouts.append(objet)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


@pytest.fixture(autouse=True)
def _graphe_reconstructible():
    graph_memory._derniere_reconstruction = None
    yield
    graph_memory._derniere_reconstruction = None


def test_mots_utiles_ecarte_les_mots_vides_et_les_courts():
    assert mots_utiles("Quelles sont les sources de la fiche sur les mitochondries") == [
        "mitochondries"
    ]


def test_mots_utiles_ne_repete_pas_un_mot():
    assert mots_utiles("Kahneman contre Kahneman") == ["kahneman", "contre"]


def test_mot_entier_refuse_une_sous_chaine():
    assert not _mot_entier("art", "particule elementaire")
    assert _mot_entier("art", "l'art de la these")


def test_as_text_dit_en_francais_qu_il_n_a_rien_trouve():
    texte = Facts([], [], 1.4).as_text()
    assert "0 faits rappeles" in texte
    assert "aucun fait du graphe ne correspond" in texte


def test_as_text_porte_la_duree_mesuree():
    faits = Facts([("a", "cites", "b", "ma-fiche")], [], 37.2)
    texte = faits.as_text()
    assert "37 ms" in texte
    assert "a --[cites]--> b" in texte
    assert "(ma-fiche)" in texte


def _fiche(slug: str, titre: str) -> BiblioCard:
    return BiblioCard(
        id=uuid.uuid4(),
        slug=slug,
        title=titre,
        description="",
        status="published",
        visibility="public",
    )


@pytest.mark.asyncio
async def test_la_fiche_est_un_seul_noeud_et_son_titre_devient_un_alias():
    fiche = _fiche("mitochondries", "Les mitochondries")
    db = _FauxSession([fiche], [])

    resume = await build_graph(db)  # type: ignore[arg-type]

    entites = [o for o in db.ajouts if isinstance(o, GraphEntity)]
    assert [e.name for e in entites] == ["mitochondries"]
    alias = [o for o in db.ajouts if isinstance(o, GraphAlias)]
    assert [(a.entity_id, a.alias) for a in alias] == [
        (entity_id("CARD", "mitochondries"), "Les mitochondries")
    ]
    assert resume["entities"] == 1
    assert db.commits == 1


@pytest.mark.asyncio
async def test_les_aretes_partent_du_noeud_de_la_fiche():
    fiche = _fiche("mitochondries", "Les mitochondries")
    source = Source(
        id=uuid.uuid4(),
        biblio_card_id=fiche.id,
        title="Nick Lane 2005",
        authors="Nick Lane",
        category="scientific_study",
    )
    db = _FauxSession([fiche], [source])

    await build_graph(db)  # type: ignore[arg-type]

    aretes = {
        (r.source_id, r.predicate, r.target_id) for r in db.ajouts if isinstance(r, GraphRelation)
    }
    fiche_eid = entity_id("CARD", "mitochondries")
    source_eid = entity_id("SOURCE", "Nick Lane 2005")
    assert (fiche_eid, "cites", source_eid) in aretes
    assert (source_eid, "authored_by", entity_id("PERSON", "Nick Lane")) in aretes


@pytest.mark.asyncio
async def test_deux_reconstructions_de_suite_sont_refusees():
    db = _FauxSession([], [])
    await build_graph(db)  # type: ignore[arg-type]

    with pytest.raises(ReconstructionTropRecenteError) as capture:
        await build_graph(_FauxSession([], []))  # type: ignore[arg-type]
    assert "global" in str(capture.value)


@pytest.mark.asyncio
async def test_forcer_passe_outre_l_ecart():
    await build_graph(_FauxSession([], []))  # type: ignore[arg-type]
    db = _FauxSession([], [])

    await build_graph(db, forcer=True)  # type: ignore[arg-type]

    assert db.commits == 1
