"""Le referencement saisi a la creation doit atteindre la fiche.

Le formulaire de creation demande format, categorie et type d'auteur. Le
schema de creation ne les acceptait pas : trois champs remplis par le createur
disparaissaient sans message, et la fiche publiee s'affichait « Non declare »
jusqu'a une edition ulterieure.
"""

from __future__ import annotations

import pytest

from app.schemas.biblio_card import CardCreate


@pytest.fixture
def donnees():
    return {
        "slug": "fiche-referencee",
        "title": "Fiche referencee",
        "platform": "revue-scientifique",
        "content_type": "article",
    }


def test_le_schema_de_creation_accepte_le_referencement(donnees):
    card = CardCreate(
        **donnees,
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    assert card.format.value == "texte"
    assert card.category.value == "article-scientifique"
    assert card.author_kind.value == "chercheur"


def test_le_referencement_reste_facultatif(donnees):
    #: « Non declare » est une reponse legitime : ne rien dire n'est pas mentir.
    card = CardCreate(**donnees)
    assert card.format is None
    assert card.category is None
    assert card.author_kind is None
