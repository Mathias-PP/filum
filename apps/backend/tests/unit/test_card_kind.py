"""Une fiche sujet ne documente aucun contenu, et le schema le rend impossible.

Avant `card_kind`, toute fiche devait declarer une plateforme et un type de
contenu : une bibliographie sur une question finissait donc en fiche qui
documente un article inexistant, avec des auteurs inventes. Le remede ne
pouvait pas etre une consigne, il fallait que le schema refuse.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.biblio_card import CardKind
from app.schemas.biblio_card import CardCreate, CardUpdate


def _sujet(**extra):
    return CardCreate(slug="pourquoi-dormir", title="Pourquoi dormir ?", card_kind="sujet", **extra)


def test_une_fiche_contenu_reste_le_defaut():
    #: Toutes les fiches anterieures documentaient un contenu : changer le
    #: defaut ferait mentir l'historique.
    card = CardCreate(slug="ma-video", title="Ma video")
    assert card.card_kind is CardKind.CONTENU


def test_une_fiche_sujet_ne_porte_aucun_champ_de_contenu():
    assert _sujet().content_url is None
    for champ, valeur in (
        ("content_url", "https://exemple.org/article"),
        ("content_authors", "Une chercheuse"),
        ("content_text", "Le texte integral."),
        ("platform", "youtube"),
        ("content_type", "video"),
    ):
        with pytest.raises(ValidationError, match="ne documente aucun contenu"):
            _sujet(**{champ: valeur})


def test_une_fiche_sujet_ne_se_revendique_pas():
    #: `is_seed` sert a reclamer une fiche creee au nom de l'auteur du contenu.
    #: Sans contenu source, il n'y a pas d'auteur tiers a qui la rendre.
    with pytest.raises(ValidationError, match="is_seed"):
        _sujet(is_seed=True)


def test_une_fiche_contenu_sans_plateforme_declaree_tombe_sur_other():
    #: `other` est la case honnete d'un contenu hors liste. L'ancien defaut
    #: `video` affirmait, lui, ce que personne n'avait declare.
    card = CardCreate(slug="ma-video", title="Ma video", content_url="https://exemple.org/a")
    assert card.platform.value == "other"
    assert card.content_type.value == "other"


def test_une_fiche_contenu_garde_ce_qui_est_declare():
    card = CardCreate(
        slug="ma-video",
        title="Ma video",
        content_url="https://youtube.com/watch?v=x",
        platform="youtube",
        content_type="video",
    )
    assert card.platform.value == "youtube"
    assert card.content_type.value == "video"


def test_la_modification_refuse_de_melanger_les_natures():
    with pytest.raises(ValidationError, match="ne documente aucun contenu"):
        CardUpdate(card_kind="sujet", platform="youtube")


def test_la_modification_vers_sujet_sans_champ_de_contenu_passe():
    modification = CardUpdate(card_kind="sujet", title="Pourquoi dormir ?")
    assert modification.card_kind is CardKind.SUJET
