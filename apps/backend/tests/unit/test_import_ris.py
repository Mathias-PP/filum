"""Import RIS et decodage LaTeX des .bib."""

from __future__ import annotations

from app.services.import_parsers import (
    detect_format,
    latex_to_unicode,
    parse_bibtex,
    parse_file,
    parse_ris,
)

RIS_MIN = """TY  - JOUR
AU  - Adleman, N.
AU  - Menon, V.
TI  - A developmental fMRI study
PY  - 2002
JO  - NeuroImage
VL  - 16
DO  - 10.1006/nimg.2002.1046
UR  - https://example.org/adleman
ER  -
"""


class TestParseRis:
    def test_lit_un_enregistrement_complet(self):
        r = parse_ris(RIS_MIN)
        assert len(r.refs) == 1
        ref = r.refs[0]
        assert ref.title == "A developmental fMRI study"
        assert ref.url == "https://example.org/adleman"
        assert ref.year == 2002
        assert ref.category == "article-scientifique"

    def test_les_auteurs_repetes_s_accumulent(self):
        # RIS met un auteur par ligne AU : n'en garder qu'un perdrait la
        # co-signature.
        assert parse_ris(RIS_MIN).refs[0].authors == "Adleman, N., Menon, V."

    def test_sans_url_le_doi_sert_de_lien(self):
        ris = "TY  - JOUR\nTI  - Sans URL\nDO  - 10.1/abc\nER  - \n"
        assert parse_ris(ris).refs[0].url == "https://doi.org/10.1/abc"

    def test_un_titre_sans_lien_reste_une_reference(self):
        # Un livre, un chapitre, un article ancien n'ont souvent aucune
        # adresse. Les ecarter ampute une bibliographie de ses references les
        # plus anciennes — mesure : 17 des 187 refs de 10.1186/s12916-019-1380-z.
        r = parse_ris("TY  - JOUR\nTI  - Un titre sans lien\nER  - \n")
        assert r.skipped == 0
        assert [(x.url, x.title) for x in r.refs] == [("", "Un titre sans lien")]

    def test_sans_url_ni_titre_l_entree_est_comptee_comme_ignoree(self):
        # Rien pour l'identifier : la compter dans `skipped` est honnete ;
        # la laisser tomber en silence ne l'est pas.
        r = parse_ris("TY  - JOUR\nPY  - 2020\nER  - \n")
        assert r.refs == []
        assert r.skipped == 1

    def test_deux_refs_sans_lien_ne_fusionnent_pas(self):
        # Sans URL, la cle de dedup ne peut pas etre l'URL : deux titres
        # distincts s'effondreraient sur une entree vide unique.
        ris = "TY  - BOOK\nTI  - Premier\nER  - \nTY  - BOOK\nTI  - Second\nER  - \n"
        assert [x.title for x in parse_ris(ris).refs] == ["Premier", "Second"]

    def test_plusieurs_enregistrements(self):
        r = parse_ris(RIS_MIN + "\n" + RIS_MIN.replace("adleman", "menon"))
        assert len(r.refs) == 2

    def test_dernier_enregistrement_sans_er_final(self):
        # Fichier tronque : la derniere reference doit compter quand meme.
        r = parse_ris("TY  - JOUR\nTI  - Tronque\nUR  - https://x.org/a\n")
        assert len(r.refs) == 1

    def test_un_ty_sans_er_ne_fond_pas_deux_references(self):
        ris = "TY  - JOUR\nTI  - Un\nUR  - https://x.org/1\nTY  - JOUR\nTI  - Deux\nUR  - https://x.org/2\n"
        r = parse_ris(ris)
        assert [ref.title for ref in r.refs] == ["Un", "Deux"]

    def test_tolere_une_ou_trois_espaces_avant_le_tiret(self):
        # La norme dit deux espaces, les exports reels varient. Etre strict
        # ferait rater des fichiers valides partout ailleurs.
        assert len(parse_ris("TY - JOUR\nTI - Un\nUR - https://x.org/a\nER - \n").refs) == 1

    def test_ignore_les_lignes_qui_ne_sont_pas_des_champs(self):
        ris = "Export EndNote\n\nTY  - JOUR\nTI  - Un\nUR  - https://x.org/a\nER  - \n"
        assert len(parse_ris(ris).refs) == 1

    def test_types_ris_vers_categories(self):
        def cat(ty):
            return parse_ris(f"TY  - {ty}\nUR  - https://x.org/a\nER  - \n").refs[0].category

        assert cat("BOOK") == "livre"
        assert cat("NEWS") == "article-presse"
        assert cat("ELEC") == "page-web"

    def test_type_inconnu_retombe_sur_page_web(self):
        # Inventer une categorie serait pire que d'avouer qu'on ne sait pas.
        assert (
            parse_ris("TY  - ZZZZ\nUR  - https://x.org/a\nER  - \n").refs[0].category == "page-web"
        )

    def test_fichier_vide(self):
        assert parse_ris("").refs == []

    def test_doublons_fusionnes(self):
        r = parse_ris(RIS_MIN + RIS_MIN)
        assert len(r.refs) == 1


class TestDetectFormat:
    def test_par_extension(self):
        assert detect_format("biblio.ris", b"") == "ris"
        assert detect_format("pubmed.nbib", b"") == "ris"

    def test_par_contenu_sans_nom_de_fichier(self):
        assert detect_format(None, RIS_MIN.encode()) == "ris"

    def test_ne_confond_pas_avec_du_markdown(self):
        # Une note qui mentionne « TY  - » en milieu de phrase n'est pas un RIS.
        md = b"# Notes\n\nJ'ai lu un export TY  - JOUR quelque part.\n"
        assert detect_format(None, md) == "markdown"

    def test_parse_file_route_vers_le_bon_parseur(self):
        r = parse_file("biblio.ris", RIS_MIN.encode())
        assert len(r.refs) == 1


class TestLatexToUnicode:
    def test_accents_courants(self):
        assert latex_to_unicode(r"caf\'e") == "café"
        assert latex_to_unicode(r"M\"uller") == "Müller"
        assert latex_to_unicode(r"Se\~norita") == "Señorita"
        assert latex_to_unicode(r"Fran\c{c}ois") == "François"

    def test_forme_avec_accolades(self):
        assert latex_to_unicode(r"\'{e}cole") == "école"

    def test_ligatures_et_lettres_sans_accent(self):
        assert latex_to_unicode(r"\ss{}") == "ß"
        assert latex_to_unicode(r"\oe{}uvre") == "œuvre"

    def test_tirets_typographiques(self):
        assert latex_to_unicode("pages 10--20") == "pages 10–20"

    def test_commande_inconnue_retiree_et_non_affichee(self):
        # « \textbf » est un artefact de format, jamais du contenu : le laisser
        # passer l'afficherait tel quel dans la fiche publique.
        assert latex_to_unicode(r"\textbf{Gras} et suite") == "Gras et suite"

    def test_accolades_de_protection_retirees(self):
        assert latex_to_unicode("{Cancer} chez la souris") == "Cancer chez la souris"

    def test_texte_ordinaire_intact(self):
        assert latex_to_unicode("Un titre normal") == "Un titre normal"

    def test_applique_a_l_import_bibtex(self):
        bib = r"""@article{x,
  title = {Le r\^ole du cortex},
  author = {L\'evy, Marie},
  url = {https://x.org/a}
}"""
        ref = parse_bibtex(bib).refs[0]
        assert ref.title == "Le rôle du cortex"
        assert "Lévy" in (ref.authors or "")


class TestAllerRetour:
    def test_ce_que_philum_exporte_philum_le_relit(self):
        # La garantie qui compte pour l'utilisateur : exporter puis reimporter
        # ne doit rien perdre.
        from types import SimpleNamespace

        from app.services.export import export_ris

        from .test_csl import make_source

        card = SimpleNamespace(
            title="Fiche",
            sources=[
                make_source(
                    title="Un titre",
                    authors="Adleman N., Menon V.",
                    url="https://x.org/a",
                    doi="10.1/abc",
                )
            ],
        )
        refs = parse_ris(export_ris(card)).refs
        assert len(refs) == 1
        assert refs[0].title == "Un titre"
        assert refs[0].url == "https://x.org/a"
        assert refs[0].authors == "Adleman, N., Menon, V."
