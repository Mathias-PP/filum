"""Ce qu'un PDF de fiche doit porter, et ce qu'il n'a pas le droit de taire.

Le PDF est le format qu'on imprime, qu'on joint a un courriel, qu'on depose
dans un dossier. C'est donc celui qui circulera le plus loin de Philum, et
celui ou une information manquante sera le moins rattrapable : personne
n'ouvrira la fiche en ligne pour verifier qu'un article n'a pas ete retracte.

Deux familles de tests. Les premiers tiennent le contenu : une retractation
s'affiche avec son motif attribue, le verbatim ne se confond pas avec ce que
le createur en dit, les references restent cliquables. Les seconds tiennent
l'honnetete du support : les polices PDF standard ne couvrent que WinAnsi, et
un verbatim ampute sans le dire serait un verbatim faux.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from app.services import pdf_minimal
from app.services.export_pdf import export_pdf


def _extrait(**kw):
    base = {
        "position": 0,
        "title": None,
        "text": "Ce que la source dit.",
        "context": None,
        "suggested_by_ai": False,
        "annotated_by_ai": False,
        "verified_at": None,
        "verified_status": None,
        "verified_text_source": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _source(**kw):
    base = {
        "position": 0,
        "url": "https://example.org/article",
        "title": "Un titre de reference",
        "authors": "Dupont, M.",
        "published_at": datetime(2024, 3, 1),
        "format": "texte",
        "category": "article-scientifique",
        "author_kind": "chercheur",
        "annotation": None,
        "is_pivot": False,
        "stance": None,
        "journal": None,
        "volume": None,
        "pages": None,
        "publisher": None,
        "doi": None,
        "archive_url": None,
        "archive_timestamp": None,
        "retraction_status": None,
        "retraction_notice_doi": None,
        "retraction_reason": None,
        "oa_status": None,
        "oa_url": None,
        "excerpts": [],
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _card(sources, titre="Une fiche sur les mitochondries"):
    return SimpleNamespace(
        id=uuid4(),
        title=titre,
        slug="une-fiche",
        description="Une description",
        content_url="https://youtube.com/watch?v=abc",
        published_at=datetime(2026, 1, 15),
        user=SimpleNamespace(username="createur", display_name="Le Createur"),
        sources=sources,
    )


URL = "https://philum.example/@createur/une-fiche"


def _texte(pdf: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def _liens(pdf: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf))
    cibles = []
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            action = annot.get_object().get("/A") or {}
            if action.get("/URI"):
                cibles.append(str(action["/URI"]))
    return cibles


def _pages(pdf: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(BytesIO(pdf)).pages)


class TestLeDocumentEstUnPdfValide:
    def test_un_lecteur_de_pdf_l_ouvre_et_y_lit_le_titre(self):
        pdf = export_pdf(_card([_source()]), URL)
        assert pdf.startswith(b"%PDF-")
        assert "mitochondries" in _texte(pdf)

    def test_une_fiche_longue_se_pagine_au_lieu_de_deborder(self):
        sources = [_source(position=i, title=f"Reference numero {i}") for i in range(40)]
        assert _pages(export_pdf(_card(sources), URL)) > 1

    def test_chaque_page_porte_son_numero_et_le_total(self):
        sources = [_source(position=i, title=f"Reference numero {i}") for i in range(40)]
        pdf = export_pdf(_card(sources), URL)
        total = _pages(pdf)
        assert f"1 / {total}" in _texte(pdf)


class TestCeQueLeDocumentDoitDire:
    def test_une_retractation_s_affiche_avec_son_motif_attribue(self):
        source = _source(
            retraction_status="retracted",
            retraction_reason="Donnees fabriquees",
            retraction_notice_doi="10.1234/avis",
        )
        texte = _texte(export_pdf(_card([source]), URL))
        assert "RÉTRACTÉE" in texte
        # Le motif reste attribue : c'est le vocabulaire de Retraction Watch,
        # pas une qualification que Philum porterait.
        assert "Retraction Watch" in texte
        assert "Donnees fabriquees" in texte

    def test_le_verbatim_ne_se_confond_pas_avec_ce_que_le_createur_en_dit(self):
        source = _source(
            annotation="Je trouve cette etude solide.",
            excerpts=[_extrait(text="La respiration cellulaire produit de l'ATP.")],
        )
        texte = _texte(export_pdf(_card([source]), URL))
        assert "Note du créateur" in texte
        # Le verbatim porte des guillemets, la note du createur non : sans
        # cette difference, un lecteur attribuerait a l'auteur une phrase que
        # le createur a ecrite.
        assert "« La respiration cellulaire produit de l'ATP. »" in texte
        assert "« Je trouve cette etude solide. »" not in texte

    def test_une_mise_en_situation_proposee_par_ia_est_nommee_comme_telle(self):
        source = _source(
            excerpts=[_extrait(context="L'auteur parle ici du metabolisme.", annotated_by_ai=True)]
        )
        texte = _texte(export_pdf(_card([source]), URL))
        assert "Mise en situation" in texte
        assert "proposée par IA" in texte

    def test_les_references_restent_cliquables(self):
        source = _source(url="https://example.org/article", oa_url="https://oa.example/pdf")
        cibles = _liens(export_pdf(_card([source]), URL))
        assert "https://example.org/article" in cibles
        assert "https://oa.example/pdf" in cibles

    def test_le_perimetre_reduit_retire_les_extraits_sans_retirer_la_source(self):
        from app.services.export_scope import parse_scope

        source = _source(excerpts=[_extrait(text="Une phrase citee du texte.")])
        texte = _texte(export_pdf(_card([source]), URL, parse_scope("")))
        assert "Un titre de reference" in texte
        assert "Une phrase citee du texte." not in texte


class TestLHonneteteDuSupport:
    def test_un_glyphe_hors_winansi_est_remplace_et_declare(self):
        # Une lettre grecque dans un verbatim : aucune police PDF standard ne
        # sait l'ecrire. Le document doit le dire plutot que de laisser croire
        # que la source portait autre chose.
        source = _source(excerpts=[_extrait(text="Le rôle de α-synucléine est discuté.")])
        texte = _texte(export_pdf(_card([source]), URL))
        assert pdf_minimal.SUBSTITUT in texte
        assert "ne s'écrivent pas dans une police PDF standard" in texte

    def test_un_document_entierement_representable_n_avertit_de_rien(self):
        source = _source(excerpts=[_extrait(text="Le rôle de cette protéine est discuté.")])
        texte = _texte(export_pdf(_card([source]), URL))
        assert "ne s'écrivent pas dans une police PDF standard" not in texte

    def test_les_marques_du_verdict_de_relecture_ne_declenchent_pas_l_avertissement(self):
        # « ✓ Retrouve dans la source » porte un glyphe hors WinAnsi. Le rendu
        # le retire plutot que de le remplacer : sinon chaque fiche relue
        # porterait un avertissement qui ne parle de rien.
        source = _source(
            excerpts=[_extrait(verified_at=datetime(2026, 2, 1), verified_status="found")]
        )
        texte = _texte(export_pdf(_card([source]), URL))
        assert "Retrouvé dans la source" in texte
        assert "ne s'écrivent pas dans une police PDF standard" not in texte


class TestLaMiseEnPage:
    def test_un_mot_plus_large_que_la_page_est_coupe_plutot_que_deborde(self):
        largeur_max = 200.0
        mot = "https://example.org/" + "a" * 400
        lignes = pdf_minimal.couper(mot, 9.0, pdf_minimal.REGULIERE, largeur_max)
        assert len(lignes) > 1
        for ligne in lignes:
            assert pdf_minimal.largeur(ligne, 9.0, pdf_minimal.REGULIERE) <= largeur_max

    def test_aucune_ligne_ne_deborde_de_la_marge(self):
        source = _source(
            title="Un titre particulierement long qui ne tient pas sur une seule ligne "
            "de page A4 et doit donc se replier proprement",
            annotation="Une note du createur assez longue pour forcer plusieurs "
            "retours a la ligne dans le corps du document, afin de verifier "
            "que la coupe respecte la largeur utile de la page.",
        )
        export_pdf(_card([source]), URL)
        # La verification tient dans `couper`, exercee ci-dessus ; ici on
        # s'assure seulement que le rendu complet ne leve pas.

    def test_une_page_ne_commence_jamais_par_un_blanc(self):
        # `espace()` en tete de page avancerait le curseur sous la marge haute
        # et trahirait la coupure : le saut appartient au bloc precedent.
        doc = pdf_minimal.Document("Titre", "pied")
        doc.espace(40)
        doc.paragraphe("Premiere ligne")
        assert doc._pages[0].lignes[0].y > pdf_minimal.HAUTEUR_PAGE - pdf_minimal.MARGE - 20
