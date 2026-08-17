"""Validation Pydantic face a des entrees malveillantes.

Les schemas sont valides tous les jours par des entrees nominales. Ce fichier
teste ce qui ne rentre PAS : slugs de path-traversal, URLs oversized, XSS
inline, chaines de longueur limite, JSON qui essaie de contourner les
constraints. Une regression qui desarme un `Field(min_length=...)` ou un
regex passerait sans alerte aujourd'hui.

Pas de dependance nouvelle (hypothesis reporte). Tests par exemples cibles
sur les schemas les plus exposes au public : SourceCreate (endpoint POST
qui accepte du contenu utilisateur libre), CardCreate (slug qui devient URL
publique), AttestationCreate (payload qui va etre signe).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.attestation import AttestationCreate
from app.schemas.biblio_card import CardCreate
from app.schemas.source import SourceCreate


def _source_payload(**overrides) -> dict:
    base = {
        "url": "https://example.org/source",
        "format": "texte",
        "category": "article-scientifique",
        "author_kind": "chercheur",
    }
    base.update(overrides)
    return base


def _card_payload(**overrides) -> dict:
    base = {
        "slug": "ma-fiche",
        "title": "Ma fiche",
    }
    base.update(overrides)
    return base


class TestSlugCard:
    """Le slug devient un fragment d'URL publique `/@user/{slug}`. Toute
    tolerance ici expose a du path traversal, du XSS sur le rendu du slug,
    ou des collisions par normalisation Unicode."""

    def test_slug_avec_slash_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="dossier/secret"))

    def test_slug_avec_double_dot_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="../autre-user"))

    def test_slug_avec_espace_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="mon slug"))

    def test_slug_avec_majuscule_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="MonSlug"))

    def test_slug_qui_commence_par_tiret_est_refuse(self):
        """`^[a-z0-9]` en tete : un slug qui commence par '-' donne des URLs
        difficiles a partager oralement (« tiret ... »)."""
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="-ma-fiche"))

    def test_slug_trop_court_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="ab"))

    def test_slug_avec_html_est_refuse(self):
        """Une balise script dans un slug passerait a travers l'URL du browser
        et pourrait etre reflete tel quel sur des surfaces peu prudentes."""
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(slug="<script>alert(1)</script>"))


class TestChampsTexteCard:
    def test_title_vide_est_refuse(self):
        """min_length=1 : un titre vide rendrait la fiche non-partageable."""
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(title=""))

    def test_title_tres_long_est_refuse(self):
        """max_length=500 : au-dela l'affichage casse partout (OG image,
        listings, meta title). Le regex Pydantic doit borner."""
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(title="x" * 501))

    def test_title_avec_html_est_accepte_tel_quel(self):
        """Le schema ne fait pas l'echappement (c'est le role du rendu Svelte).
        Ce test fige le contrat : le stockage garde le texte brut, l'echappement
        est cote frontend."""
        card = CardCreate(**_card_payload(title="<b>Vrai gras</b>"))
        assert card.title == "<b>Vrai gras</b>"

    def test_content_authors_tres_long_est_refuse(self):
        with pytest.raises(ValidationError):
            CardCreate(**_card_payload(content_authors="x" * 501))


class TestChampsSourceCreate:
    def test_url_tres_longue_est_refusee(self):
        """max_length=2000 : au-dela ce n'est plus une URL utilisable, et
        stocker 10 MB de "URL" par ligne cassait la base."""
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(url="https://x.org/" + "a" * 3000))

    def test_title_source_tres_long_est_refuse(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(title="x" * 501))

    def test_authors_source_tres_long_est_refuse(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(authors="x" * 501))

    def test_annotation_tres_longue_est_refusee(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(annotation="x" * 501))

    def test_doi_tres_long_est_refuse(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(doi="10.1000/" + "a" * 300))

    def test_categorie_hors_enum_est_refusee(self):
        """L'enum Pydantic doit refuser une valeur inconnue. Sans, une source
        de categorie « random » traverserait le stack et casserait les
        agregations frontend."""
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(category="random"))

    def test_author_kind_hors_enum_est_refuse(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(author_kind="magicien"))

    def test_format_hors_enum_est_refuse(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(format="hologramme"))

    def test_stance_hors_enum_est_refusee(self):
        with pytest.raises(ValidationError):
            SourceCreate(**_source_payload(stance="chelou"))

    def test_champ_inconnu_est_ignore_par_defaut(self):
        """Pydantic tolere par defaut les champs supplementaires. On documente
        ici le comportement : le champ inconnu est droppe silencieusement.
        `SourceUpdate` a `extra=forbid`, pas `SourceCreate` -- si un jour ca
        change, ce test le fera savoir explicitement."""
        s = SourceCreate(**_source_payload(champ_invente="valeur"))
        assert not hasattr(s, "champ_invente")


class TestAttestationCreate:
    """Le contenu attesté part signé : toute laxite ici s'imprime dans la
    signature Ed25519 et devient permanente."""

    def test_content_url_vide_est_refusee(self):
        with pytest.raises(ValidationError):
            AttestationCreate(content_url="")

    def test_content_url_manquante_est_refusee(self):
        with pytest.raises(ValidationError):
            AttestationCreate()  # type: ignore[call-arg]

    def test_content_url_ordinaire_est_acceptee(self):
        payload = AttestationCreate(content_url="https://ex.org/mon-contenu")
        assert payload.content_url == "https://ex.org/mon-contenu"
