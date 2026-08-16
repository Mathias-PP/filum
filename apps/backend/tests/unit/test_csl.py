"""Le pivot CSL, et surtout le decoupage des noms d'auteurs."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.csl import (
    author_display,
    csl_key,
    parse_authors,
    parse_name,
    to_csl,
)


def make_source(**kw):
    base = dict(
        position=1,
        title="Un titre",
        authors=None,
        url="https://example.org/a",
        published_at=None,
        format="article",
        category="article-scientifique",
        author_kind="chercheur",
        is_pivot=False,
        annotation=None,
        journal=None,
        volume=None,
        pages=None,
        publisher=None,
        doi=None,
        archive_url=None,
        archive_timestamp=None,
        stance=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestParseName:
    @pytest.mark.parametrize(
        "entry,family,given",
        [
            # La forme majoritaire des donnees reelles (OpenAlex, Crossref).
            ("Adleman N.", "Adleman", "N."),
            ("Adleman N. J.", "Adleman", "N. J."),
            # La meme personne, ecrite a l'envers : doit donner le meme verdict.
            ("N. Adleman", "Adleman", "N."),
            ("J. A. Smith", "Smith", "J. A."),
            # Forme explicite, sans ambiguite possible.
            ("Dupont, Jean", "Dupont", "Jean"),
            # Convention occidentale quand aucune initiale ne marque le nom.
            ("Jean Dupont", "Dupont", "Jean"),
            # Un nom compose ne doit pas perdre sa premiere moitie.
            ("Lewis-Peacock J.", "Lewis-Peacock", "J."),
            ("van der Berg M.", "van der Berg", "M."),
        ],
    )
    def test_decoupe(self, entry, family, given):
        assert parse_name(entry) == {"family": family, "given": given}

    def test_un_seul_mot_reste_un_nom_de_famille(self):
        # « Aron » existe tel quel en base. Lui inventer un prenom vide
        # ferait apparaitre un auteur « Aron, » dans Zotero.
        assert parse_name("Aron") == {"family": "Aron"}

    def test_chaine_vide_ne_produit_pas_d_auteur_fantome(self):
        assert parse_name("   ") == {}


class TestParseAuthors:
    def test_liste_famille_initiales(self):
        names = parse_authors("Adleman N., Menon V., Blasey C.")
        assert [n["family"] for n in names] == ["Adleman", "Menon", "Blasey"]
        assert [n["given"] for n in names] == ["N.", "V.", "C."]

    def test_un_seul_auteur_en_famille_virgule_initiales(self):
        # Le piege central : « Dupont, J. » est UN auteur, pas deux. Une
        # virgule suivie de simples initiales est forcement interne.
        assert parse_authors("Dupont, J.") == [{"family": "Dupont", "given": "J."}]

    def test_plusieurs_auteurs_en_famille_virgule_initiales(self):
        names = parse_authors("Dupont, J., Martin, A.")
        assert names == [
            {"family": "Dupont", "given": "J."},
            {"family": "Martin", "given": "A."},
        ]

    def test_le_point_virgule_prime_sur_la_virgule(self):
        # Avec un point-virgule, la virgule ne peut etre qu'interne : on ne
        # doit plus deviner quoi que ce soit.
        names = parse_authors("Dupont, Jean; Martin, Anne")
        assert names == [
            {"family": "Dupont", "given": "Jean"},
            {"family": "Martin", "given": "Anne"},
        ]

    def test_famille_virgule_prenom_reste_un_seul_auteur(self):
        # Saisie manuelle courante. Le decouper en deux ferait apparaitre
        # « Marie » comme co-auteur dans Zotero.
        assert parse_authors("Dupont, Marie") == [{"family": "Dupont", "given": "Marie"}]

    def test_paires_famille_prenom_en_serie(self):
        assert parse_authors("Dupont, Marie, Martin, Anne") == [
            {"family": "Dupont", "given": "Marie"},
            {"family": "Martin", "given": "Anne"},
        ]

    def test_le_pari_des_paires_ne_s_applique_pas_aux_noms_composes(self):
        # « Adleman N. » contient une espace : ce n'est pas un mono-mot, la
        # regle des paires ne doit pas s'y appliquer.
        names = parse_authors("Adleman N., Menon V.")
        assert len(names) == 2

    def test_nombre_impair_de_mono_mots_reste_une_liste(self):
        # Trois mono-mots ne peuvent pas etre des paires : ce sont trois noms.
        assert [n["family"] for n in parse_authors("Bell, Aron, Amso")] == [
            "Bell",
            "Aron",
            "Amso",
        ]

    def test_auteur_unique_sans_prenom(self):
        assert parse_authors("Aron") == [{"family": "Aron"}]

    def test_rien_a_lire_ne_donne_aucun_auteur(self):
        # Une liste d'auteurs vide vaut mieux qu'un auteur vide : CSL
        # afficherait une virgule orpheline dans la bibliographie.
        assert parse_authors(None) == []
        assert parse_authors("") == []
        assert parse_authors("  ,  ; ") == []

    def test_et_al_n_est_pas_un_auteur(self):
        # Constate en prod sur la fiche vitrine : l'export BibTeX portait
        # `@article{al2010n2}` et le RIS `AU  - al., Brian J. Wiltgen et`.
        # La regle « dernier jeton = famille » prenait l'abreviation pour
        # un nom, et l'auteur reel disparaissait dans le prenom.
        assert parse_authors("Brian J. Wiltgen et al.") == [
            {"family": "Wiltgen", "given": "Brian J."}
        ]

    def test_et_al_en_queue_de_liste_ne_cree_pas_d_auteur_fantome(self):
        names = parse_authors("Xu Liu, Steve Ramirez, Susumu Tonegawa et al.")
        assert [n["family"] for n in names] == ["Liu", "Ramirez", "Tonegawa"]

    def test_et_al_detache_par_une_virgule(self):
        assert parse_authors("Nader K., et al.") == [{"family": "Nader", "given": "K."}]

    def test_les_variantes_francaises_sont_reconnues(self):
        assert parse_authors("Dupont et coll.") == [{"family": "Dupont"}]
        assert parse_authors("Dupont et autres") == [{"family": "Dupont"}]

    def test_un_nom_qui_commence_par_al_reste_intact(self):
        # « Al » est une particule frequente. La couper produirait un auteur
        # tronque a chaque export.
        assert parse_authors("Mohammed Al Fayed") == [{"family": "Fayed", "given": "Mohammed Al"}]

    def test_espaces_superflus_absorbes(self):
        assert parse_authors("  Adleman   N.  ,  Menon V. ") == [
            {"family": "Adleman", "given": "N."},
            {"family": "Menon", "given": "V."},
        ]


class TestCslKey:
    def test_utilise_le_nom_de_famille_et_l_annee(self):
        s = make_source(authors="Adleman N., Menon V.", published_at=datetime(2012, 5, 1))
        assert csl_key(s, 3) == "adleman2012n3"

    def test_sans_date_la_cle_le_dit(self):
        # « nd » (no date) plutot qu'une annee inventee.
        s = make_source(authors="Aron")
        assert csl_key(s, 1) == "aron ndn1".replace(" ", "")

    def test_la_cle_ne_cite_pas_une_abreviation(self):
        # `al2010n2` etait la cle servie en production : elle designait
        # « et al. » comme auteur cite.
        s = make_source(authors="Brian J. Wiltgen et al.", published_at=datetime(2010, 1, 1))
        assert csl_key(s, 2) == "wiltgen2010n2"

    def test_sans_auteur_retombe_sur_le_titre(self):
        s = make_source(authors=None, title="Memoire et cerveau")
        assert csl_key(s, 1).startswith("memoire")

    def test_cle_toujours_alphanumerique(self):
        # Une cle BibTeX avec un accent ou une espace casse le .bib.
        s = make_source(authors="Éric Lévy-Bühler", published_at=datetime(2020, 1, 1))
        key = csl_key(s, 1)
        assert key.replace("n1", "").isalnum() or key.isalnum()
        assert " " not in key


class TestToCsl:
    def test_champs_de_base(self):
        s = make_source(
            title="Inhibitory control",
            url="https://x.org/a",
            doi="10.1/abc",
            journal="Front. Psychol.",
            volume="13",
            pages="1-12",
            published_at=datetime(2022, 3, 14),
        )
        item = to_csl(s, 1)
        assert item["title"] == "Inhibitory control"
        assert item["URL"] == "https://x.org/a"
        assert item["DOI"] == "10.1/abc"
        assert item["container-title"] == "Front. Psychol."
        assert item["issued"] == {"date-parts": [[2022, 3, 14]]}

    def test_type_csl_ferme(self):
        # CSL a un vocabulaire ferme : une categorie inconnue doit retomber
        # sur « webpage », pas sortir un type que personne ne sait lire.
        assert to_csl(make_source(category="podcast"), 1)["type"] == "broadcast"
        assert to_csl(make_source(category="livre"), 1)["type"] == "book"
        assert to_csl(make_source(category="autre-chose"), 1)["type"] == "webpage"

    def test_un_champ_absent_n_apparait_pas(self):
        # Un "DOI": "" ferait croire a Zotero qu'un DOI vide existe.
        item = to_csl(make_source(), 1)
        for absent in ("DOI", "container-title", "volume", "page", "publisher", "author"):
            assert absent not in item

    def test_titre_absent_retombe_sur_l_url(self):
        item = to_csl(make_source(title=None), 1)
        assert item["title"] == "https://example.org/a"

    def test_la_position_declaree_survit_dans_note(self):
        # Zotero n'interprete pas « philum-stance », mais il le conserve :
        # l'information revient intacte d'un aller-retour.
        item = to_csl(make_source(stance="nuance-contredit"), 1)
        assert "philum-stance: nuance-contredit" in item["note"]

    def test_annotation_et_stance_cohabitent(self):
        item = to_csl(make_source(annotation="Lu en diagonale", stance="appuie"), 1)
        assert "Lu en diagonale" in item["note"]
        assert "philum-stance: appuie" in item["note"]


class TestAuthorDisplay:
    def test_rend_famille_prenom(self):
        assert author_display([{"family": "Dupont", "given": "J."}]) == "Dupont, J."

    def test_sans_prenom_pas_de_virgule_orpheline(self):
        assert author_display([{"family": "Aron"}]) == "Aron"

    def test_liste_vide(self):
        assert author_display([]) == ""
