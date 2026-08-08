"""Ce qu'un export doit encore porter quand il n'est ni JSON ni Markdown.

Une fiche Philum ne se resume pas a une liste de references : elle porte des
extraits verbatim, un verdict de relecture, une position declaree, un statut de
retractation, et un voisinage ou le *degre* dit si une fiche est citee
directement ou atteinte par ricochet.

Le JSON et le Markdown disaient tout cela. Le tableur et le Word n'en disaient
qu'une part — et c'est precisement ce que les gens telechargent pour travailler
hors ligne. Un lecteur qui ouvre le Word n'ira pas verifier ailleurs qu'un
article a ete retracte ; taire l'information la ou personne ne peut la
recouper est le pire endroit ou la taire.

Les tests ci-dessous tiennent donc une seule regle : **aucun format ne perd
d'information que le format lui-meme rend impossible a porter.** Le CSV n'a
qu'une table, il n'aura jamais les extraits ; le XLSX a des feuilles, il les
aura ; le Word a des paragraphes, il aura tout.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4


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
        "anchor_prefix": None,
        "anchor_suffix": None,
        "anchor_offset": None,
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
        "oa_status": None,
        "oa_url": None,
        "excerpts": [],
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _card(sources, titre="Une fiche", slug="une-fiche", username="createur"):
    return SimpleNamespace(
        id=uuid4(),
        title=titre,
        slug=slug,
        description="Une description",
        content_url="https://youtube.com/watch?v=abc",
        published_at=datetime(2026, 1, 15),
        user=SimpleNamespace(username=username, display_name="Le Createur"),
        sources=sources,
    )


URL = "https://philum.example/@createur/une-fiche"


def _voisinage(*, cited=(), citing=(), truncated=False):
    from app.services.export_neighbourhood import Neighbourhood

    return Neighbourhood(cited=list(cited), citing=list(citing), truncated=truncated)


def _voisine(degre: int, titre: str, scope=None, direction="cited"):
    from app.services.export_neighbourhood import NeighbourCard
    from app.services.export_scope import FULL

    return NeighbourCard(
        card=_card([_source()], titre=titre, slug=titre.lower().replace(" ", "-")),
        degree=degre,
        direction=direction,
        scope=scope or FULL,
    )


def _feuilles(classeur: bytes) -> dict[str, str]:
    """Nom de feuille -> XML, tel que le classeur les declare."""
    with zipfile.ZipFile(BytesIO(classeur)) as zf:
        workbook = zf.read("xl/workbook.xml").decode()
        noms = [
            morceau.split('name="', 1)[1].split('"', 1)[0]
            for morceau in workbook.split("<sheet ")[1:]
        ]
        return {
            nom: zf.read(f"xl/worksheets/sheet{i}.xml").decode()
            for i, nom in enumerate(noms, start=1)
        }


def _texte_docx(document: bytes) -> str:
    with zipfile.ZipFile(BytesIO(document)) as zf:
        return zf.read("word/document.xml").decode()


class TestLeTableurPorteLesDegres:
    """Le manque nomme par l'utilisateur : « les degres ne sont pas exportables ».

    Un tableau de sources n'a pas de colonne ou loger une fiche voisine. La
    reponse n'est pas de renoncer mais de lui donner sa feuille, avec le degre
    en colonne — sans quoi un voisinage a deux degres s'aplatit en une liste ou
    plus rien ne distingue le proche du lointain.
    """

    def test_les_fiches_voisines_ont_leur_feuille(self):
        from app.services.export import export_xlsx

        classeur = export_xlsx(
            _card([_source()]),
            neighbourhood=_voisinage(cited=[_voisine(1, "Fiche proche")]),
            base_url="https://philum.example",
        )
        assert "Fiches voisines" in _feuilles(classeur)

    def test_le_degre_distingue_le_proche_du_lointain(self):
        from app.services.export import export_xlsx

        classeur = export_xlsx(
            _card([_source()]),
            neighbourhood=_voisinage(
                cited=[_voisine(1, "Fiche proche"), _voisine(2, "Fiche lointaine")]
            ),
            base_url="https://philum.example",
        )
        feuille = _feuilles(classeur)["Fiches voisines"]
        assert "degree" in feuille
        # Chaque voisine porte son degre sur sa propre ligne : les confondre
        # donnerait le meme poids a une fiche citee et a un ricochet.
        lignes = {
            titre: ligne
            for ligne in feuille.split("<row ")
            for titre in ("Fiche proche", "Fiche lointaine")
            if titre in ligne
        }
        assert ">1</t>" in lignes["Fiche proche"]
        assert ">2</t>" in lignes["Fiche lointaine"]
        assert ">2</t>" not in lignes["Fiche proche"]

    def test_le_sens_de_la_relation_se_lit(self):
        # « citee par celle-ci » et « cite celle-ci » ne sont pas deux valeurs
        # d'un meme attribut : ce sont deux relations opposees.
        from app.services.export import export_xlsx

        classeur = export_xlsx(
            _card([_source()]),
            neighbourhood=_voisinage(citing=[_voisine(1, "Fiche citante")]),
            base_url="https://philum.example",
        )
        assert "cite celle-ci" in _feuilles(classeur)["Fiches voisines"]

    def test_les_sources_des_voisines_partent_aussi(self):
        """On ne va pas chercher une fiche voisine pour son titre.

        La feuille « Fiches voisines » ne porte que des metadonnees de fiche :
        s'en tenir la ferait d'un degre demande une promesse creuse.
        """
        from app.services.export import export_xlsx

        classeur = export_xlsx(
            _card([_source()]),
            neighbourhood=_voisinage(cited=[_voisine(1, "Fiche proche")]),
            base_url="https://philum.example",
        )
        feuille = _feuilles(classeur)["Sources des voisines"]
        assert "Fiche proche" in feuille
        assert "https://example.org/article" in feuille

    def test_un_degre_moins_genereux_garde_ses_colonnes_vides(self):
        """Une feuille n'a qu'un en-tete, et les degres n'ont pas le meme
        perimetre. La forme vient du plus large ; ce qu'un degre exclut se rend
        vide, jamais absent — sinon les lignes se decaleraient."""
        from app.services.export import export_xlsx
        from app.services.export_scope import parse_scope

        classeur = export_xlsx(
            _card([_source()]),
            neighbourhood=_voisinage(
                cited=[
                    _voisine(1, "Fiche large"),
                    _voisine(2, "Fiche etroite", scope=parse_scope("")),
                ]
            ),
            base_url="https://philum.example",
        )
        feuille = _feuilles(classeur)["Sources des voisines"]
        assert "retraction_status" in feuille
        largeurs = {ligne.count("<c ") for ligne in feuille.split("<row ")[1:] if "<c " in ligne}
        assert len(largeurs) == 1

    def test_sans_voisinage_demande_pas_de_feuille_vide(self):
        # Une feuille vide ferait croire que la fiche n'a pas de voisines,
        # alors qu'on ne les a pas cherchees.
        from app.services.export import export_xlsx

        assert "Fiches voisines" not in _feuilles(export_xlsx(_card([_source()])))


class TestLeTableurPorteLesExtraits:
    def test_les_extraits_ont_leur_feuille(self):
        from app.services.export import export_xlsx

        source = _source(excerpts=[_extrait(text="Un passage cite.")])
        feuilles = _feuilles(export_xlsx(_card([source])))
        assert "Un passage cite." in feuilles["Extraits"]

    def test_la_mise_en_situation_a_sa_propre_colonne(self):
        """Recollee au texte, elle passerait pour du verbatim."""
        from app.services.export import EXCERPT_COLUMNS, export_xlsx

        source = _source(excerpts=[_extrait(text="Un passage cite.", context="Situe le passage.")])
        feuille = _feuilles(export_xlsx(_card([source])))["Extraits"]
        assert EXCERPT_COLUMNS.index("context") != EXCERPT_COLUMNS.index("text")
        assert "Un passage cite.</t>" in feuille
        assert "Situe le passage.</t>" in feuille

    def test_l_origine_de_l_annotation_se_sait(self):
        from app.services.export import export_xlsx

        source = _source(excerpts=[_extrait(context="Situe le passage.", annotated_by_ai=True)])
        feuille = _feuilles(export_xlsx(_card([source])))["Extraits"]
        assert "annotated_by_ai" in feuille
        assert ">oui<" in feuille

    def test_un_perimetre_sans_extraits_n_a_pas_la_feuille(self):
        from app.services.export import export_xlsx
        from app.services.export_scope import parse_scope

        source = _source(excerpts=[_extrait()])
        feuilles = _feuilles(export_xlsx(_card([source]), parse_scope("")))
        assert "Extraits" not in feuilles


class TestLeTableurPorteLaFiabilite:
    def test_la_retractation_a_une_colonne(self):
        from app.services.export import export_xlsx

        source = _source(retraction_status="retracted", retraction_notice_doi="10.1/avis")
        feuille = _feuilles(export_xlsx(_card([source])))["Sources"]
        assert "retracted" in feuille
        assert "10.1/avis" in feuille

    def test_la_position_declaree_a_une_colonne(self):
        from app.services.export import export_csv

        csv = export_csv(_card([_source(stance="nuance-contredit")]))
        assert "stance" in csv.splitlines()[0]
        assert "nuance-contredit" in csv

    def test_un_perimetre_reduit_vide_la_colonne_sans_la_retirer(self):
        """Une colonne absente se lit « le format ne sait pas » ; une colonne
        vide se lit « rien a dire ». La seconde est la verite ici."""
        from app.services.export import export_csv
        from app.services.export_scope import parse_scope

        csv = export_csv(_card([_source(annotation="Une note")]), parse_scope(""))
        assert "annotation" in csv.splitlines()[0]
        assert "Une note" not in csv


class TestLeWordDitCeQuiEngageLeLecteur:
    """Le Word se lit hors ligne : c'est le pire endroit ou taire un verdict."""

    def test_la_retractation_est_ecrite_en_toutes_lettres(self):
        from app.services.export import export_docx

        source = _source(retraction_status="retracted", retraction_notice_doi="10.1/avis")
        texte = _texte_docx(export_docx(_card([source]), URL))
        assert "RÉTRACTÉE" in texte
        assert "10.1/avis" in texte

    def test_l_acces_ouvert_donne_son_adresse(self):
        # Sans l'URL, dire « acces ouvert » n'ouvre aucune porte.
        from app.services.export import export_docx

        source = _source(oa_status="green", oa_url="https://hal.example/doc.pdf")
        texte = _texte_docx(export_docx(_card([source]), URL))
        assert "https://hal.example/doc.pdf" in texte

    def test_la_position_declaree_se_lit(self):
        from app.services.export import export_docx

        texte = _texte_docx(export_docx(_card([_source(stance="appuie")]), URL))
        assert "Position déclarée" in texte

    def test_le_doi_part_avec_la_source(self):
        from app.services.export import export_docx

        texte = _texte_docx(export_docx(_card([_source(doi="10.1234/abcd")]), URL))
        assert "10.1234/abcd" in texte

    def test_les_fiches_voisines_gardent_leur_degre(self):
        from app.services.export import export_docx

        document = export_docx(
            _card([_source()]),
            URL,
            neighbourhood=_voisinage(
                cited=[_voisine(1, "Fiche proche"), _voisine(2, "Fiche lointaine")]
            ),
        )
        texte = _texte_docx(document)
        assert "Degré 1" in texte
        assert "Degré 2" in texte
        assert texte.index("Fiche proche") < texte.index("Degré 2")

    def test_la_mise_en_situation_ne_se_recolle_pas_dans_la_citation(self):
        from app.services.export import export_docx

        source = _source(
            excerpts=[_extrait(text="Ce que la source dit.", context="Ce qui la situe.")]
        )
        texte = _texte_docx(export_docx(_card([source]), URL))
        # Le verbatim reste borne par ses guillemets, la mise en situation dehors.
        assert "« Ce que la source dit. »" in texte
        assert "« Ce que la source dit. Ce qui la situe. »" not in texte
        assert "Ce qui la situe." in texte

    def test_le_verdict_de_relecture_voyage(self):
        from app.services.export import export_docx

        source = _source(
            excerpts=[_extrait(verified_at=datetime(2026, 8, 8), verified_status="found")]
        )
        texte = _texte_docx(export_docx(_card([source]), URL))
        assert "2026-08-08" in texte

    def test_jamais_relu_ne_dit_rien_plutot_que_de_rassurer(self):
        """Un extrait jamais relu ne porte aucune ligne : ecrire « jamais relu »
        sous chacun noierait les verdicts qui, eux, apprennent quelque chose."""
        from app.services.export import export_docx

        texte = _texte_docx(export_docx(_card([_source(excerpts=[_extrait()])]), URL))
        assert "Relu" not in texte
