"""Le pivot CSL, et surtout le decoupage des noms d'auteurs."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.csl import (
    author_display,
    csl_key,
    est_abrege,
    noms_propres,
    parse_authors,
    parse_name,
    to_csl,
)


def make_source(**kw):
    base = {
        "position": 1,
        "title": "Un titre",
        "authors": None,
        "url": "https://example.org/a",
        "published_at": None,
        "format": "article",
        "category": "article-scientifique",
        "author_kind": "chercheur",
        "is_pivot": False,
        "annotation": None,
        "journal": None,
        "volume": None,
        "pages": None,
        "publisher": None,
        "doi": None,
        "archive_url": None,
        "archive_timestamp": None,
        "stance": None,
    }
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
        assert noms_propres(parse_authors("Brian J. Wiltgen et al.")) == [
            {"family": "Wiltgen", "given": "Brian J."}
        ]

    def test_et_al_reste_lisible_comme_abreviation(self):
        # La supprimer ferait passer un article collectif pour un article a
        # auteur unique : la reference attribuerait a une personne ce que
        # plusieurs ont ecrit.
        names = parse_authors("Brian J. Wiltgen et al.")
        assert est_abrege(names)
        assert names[-1] == {"literal": "et al."}

    def test_une_liste_complete_ne_se_dit_pas_abregee(self):
        assert not est_abrege(parse_authors("Dupont, J., Martin, A."))

    def test_et_al_en_queue_de_liste_ne_cree_pas_d_auteur_fantome(self):
        names = noms_propres(parse_authors("Xu Liu, Steve Ramirez, Susumu Tonegawa et al."))
        assert [n["family"] for n in names] == ["Liu", "Ramirez", "Tonegawa"]

    def test_et_al_detache_par_une_virgule(self):
        assert noms_propres(parse_authors("Nader K., et al.")) == [
            {"family": "Nader", "given": "K."}
        ]

    def test_les_variantes_francaises_sont_reconnues(self):
        for chaine in ("Dupont et coll.", "Dupont et autres"):
            names = parse_authors(chaine)
            assert noms_propres(names) == [{"family": "Dupont"}]
            assert est_abrege(names)

    def test_un_nom_avec_particule_al_garde_la_particule_dans_la_famille(self):
        # « Al » est l'article arabe : culturellement partie du nom de famille,
        # au meme titre que « van », « de » ou « von ». Le laisser filer dans
        # le given produisait « Fayed, M.A. » en rendu APA -- une initiale
        # inventee. Meme regle pour les particules europeennes.
        assert parse_authors("Mohammed Al Fayed") == [{"family": "Al Fayed", "given": "Mohammed"}]
        assert parse_authors("Ludwig van Beethoven") == [
            {"family": "van Beethoven", "given": "Ludwig"}
        ]

    def test_espaces_superflus_absorbes(self):
        assert parse_authors("  Adleman   N.  ,  Menon V. ") == [
            {"family": "Adleman", "given": "N."},
            {"family": "Menon", "given": "V."},
        ]


class TestSeparateursDauteurs:
    """`&` et « and » sont des separateurs universels d'auteurs.

    Sans cette reconnaissance, « Redondo & Morris » restait UN seul auteur
    et la reference Harvard sortait « Morris, R.L.R.&.R.G.M. » -- l'esperluette
    devenant une initiale. Mesure sur la fiche Ca-sert-a-quoi-de-dormir en
    prod le 2026-08-18.
    """

    def test_esperluette_separe_deux_auteurs(self):
        assert parse_authors("Roger L. Redondo & Richard G. M. Morris") == [
            {"family": "Redondo", "given": "Roger L."},
            {"family": "Morris", "given": "Richard G. M."},
        ]

    def test_and_separe_deux_auteurs(self):
        assert parse_authors("Fasano A and Catassi C") == [
            {"family": "Fasano", "given": "A"},
            {"family": "Catassi", "given": "C"},
        ]

    def test_liste_mixte_virgule_esperluette(self):
        # Convention frequente : « A, B, C & D ». La normalisation & -> ; doit
        # laisser la virgule agir sur la partie gauche.
        noms = parse_authors("Rogerson T., Cai D., Frank A. & Silva A.")
        assert [n["family"] for n in noms] == ["Rogerson", "Cai", "Frank", "Silva"]


class TestInstitutions:
    """Une source signee par une organisation doit citer l'organisation.

    Sans detection, « American Nuclear Society » se parsait « Society, A.N. »
    dans la reference Harvard : une attribution fausse (personne ne s'appelle
    Society A.N.) qui rendait chaque source institutionnelle illisible.
    Mesure sur la fiche WEST-contributions-iter en prod le 2026-08-18.
    """

    def test_organisation_est_literal(self):
        assert parse_authors("American Nuclear Society") == [
            {"literal": "American Nuclear Society"}
        ]

    def test_organisation_avec_ville_est_literal(self):
        assert parse_authors("CEA Cadarache") == [{"literal": "CEA Cadarache"}]

    def test_sigle_seul_est_literal(self):
        assert parse_authors("AFP") == [{"literal": "AFP"}]
        assert parse_authors("EUROfusion") == [{"literal": "EUROfusion"}]

    def test_acronyme_compose_est_literal(self):
        assert parse_authors("CEA-IRFM") == [{"literal": "CEA-IRFM"}]

    def test_institution_dans_une_liste_reste_intacte(self):
        noms = parse_authors(
            "Bucalossi J., Ekedahl A. et al., EUROfusion Tokamak Exploitation Team"
        )
        # Deux personnes + une institution + le marqueur « et al. » d'abrege.
        propres = noms_propres(noms)
        assert propres[0] == {"family": "Bucalossi", "given": "J."}
        assert propres[1] == {"family": "Ekedahl", "given": "A."}
        assert propres[2] == {"literal": "EUROfusion Tokamak Exploitation Team"}


class TestParticules:
    """Les particules nobiliaires appartiennent au nom de famille.

    « HC van den Broeck » se lisait « Broeck, H.V.D. » : les particules « van
    den » etaient transformees en initiales, produisant deux fausses initiales
    et amputant le nom. Mesure sur la fiche celiac-disease en prod le
    2026-08-18.
    """

    def test_van_den_reste_avec_la_famille(self):
        assert parse_authors("HC van den Broeck") == [{"family": "van den Broeck", "given": "HC"}]

    def test_de_reste_avec_la_famille(self):
        assert parse_authors("Ludwig van Beethoven") == [
            {"family": "van Beethoven", "given": "Ludwig"}
        ]

    def test_particule_en_convention_occidentale(self):
        # « Jean de la Fontaine » : particules avant le dernier mot, tirees.
        assert parse_authors("Jean de la Fontaine") == [
            {"family": "de la Fontaine", "given": "Jean"}
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
