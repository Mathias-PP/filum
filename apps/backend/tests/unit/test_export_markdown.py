"""Le markdown d'une fiche doit porter de quoi *verifier*, pas seulement de quoi citer.

C'est le format qu'un agent conversationnel sait lire sans effort, et c'est
donc lui qui decide de ce qu'une IA saura dire d'une source. Une reference
retractee citee comme valide est le pire resultat possible pour Philum :
l'information de retractation, l'acces ouvert, l'archive et le DOI doivent
apparaitre dans le document, pas seulement dans l'interface.

Contrainte de forme : Philum reimporte son propre markdown (`parse_markdown`
recolte tout lien et toute URL nue). Les metadonnees ajoutees ici s'ecrivent
donc en texte, sans lien, sous peine de faire naitre une source fantome a
chaque aller-retour.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4


def _source(**kw):
    base = {
        "position": 0,
        "url": "https://doi.org/10.1234/abcd",
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
        "publisher": None,
        "volume": None,
        "pages": None,
        "doi": None,
        "archive_url": None,
        "retraction_status": None,
        "retraction_notice_doi": None,
        "oa_status": None,
        "oa_url": None,
        "excerpts": [],
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _card(sources):
    return SimpleNamespace(
        id=uuid4(),
        title="Une fiche",
        description="Une description",
        content_url="https://youtube.com/watch?v=abc",
        published_at=datetime(2026, 1, 15),
        user=SimpleNamespace(username="createur", display_name="Le Createur"),
        sources=sources,
    )


URL = "https://philum.example/@createur/une-fiche"


def _md(**source_kw) -> str:
    from app.services.export import export_markdown

    return export_markdown(_card([_source(**source_kw)]), URL)


class TestRetractation:
    """Le signal qui distingue Philum d'une simple liste de liens."""

    def test_une_source_retractee_le_dit(self):
        body = _md(retraction_status="retracted")
        assert "RÉTRACTÉE" in body

    def test_l_avis_de_retractation_est_cite(self):
        body = _md(retraction_status="retracted", retraction_notice_doi="10.1234/notice")
        assert "10.1234/notice" in body

    def test_une_source_saine_n_alarme_pas(self):
        assert "RÉTRACTÉE" not in _md(retraction_status="none")

    def test_seule_une_retractation_avérée_apparait_sous_la_source(self):
        """Mesure sur une fiche reelle : « vérification impossible » etait vrai
        des 185 sources et ajoutait 370 lignes n'affirmant rien. Sous une
        source, on ne met que des faits etablis."""
        for statut in (None, "none", "unverifiable"):
            assert "  - ⚠️" not in _md(retraction_status=statut)


class TestBilanDeFiabilite:
    """Rien n'est tu : ce que la source ne dit plus, le bilan le compte."""

    def test_les_etats_de_verification_sont_comptes_en_tete(self):
        body = _md(retraction_status="unverifiable")
        assert "## Fiabilité des sources" in body
        assert "1 non vérifiable(s)" in body

    def test_jamais_verifie_et_verifie_sans_rien_trouver_ne_se_confondent_pas(self):
        jamais = _md(retraction_status=None)
        verifie = _md(retraction_status="none")
        assert "1 jamais vérifiée(s)" in jamais
        assert "1 vérifiée(s) sans rétractation" in verifie
        assert jamais != verifie

    def test_le_bilan_compte_l_acces_ouvert_reellement_disponible(self):
        body = _md(oa_status="gold", oa_url="https://example.org/pdf")
        assert "1 en accès ouvert" in body

    def test_un_podcast_n_est_pas_compte_comme_non_verifiable(self):
        """Une revue retracte un article, pas un podcast.

        La fiche vitrine annoncait « 13 non vérifiable(s) » sur 18 sources : le
        chiffre se lisait comme un doute sur les sources alors que la question
        ne se posait pas. Meme regle que l'interface depuis la PR #418.
        """
        body = _md(category="podcast", retraction_status="unverifiable")
        assert "non vérifiable(s)" not in body

    def test_le_bilan_de_retractation_dit_sur_quoi_il_porte(self):
        from app.services.export import export_markdown

        card = _card(
            [
                _source(category="article-scientifique", retraction_status="none"),
                _source(category="podcast", retraction_status="unverifiable"),
            ]
        )
        body = export_markdown(card, URL)
        assert "Sur 2 source(s)" in body
        assert "Rétractation (1 source(s) de littérature scientifique)" in body
        assert "1 vérifiée(s) sans rétractation" in body

    def test_un_avis_publie_compte_meme_hors_litterature(self):
        """Un billet qui relaie un article retracte doit pouvoir le dire."""
        body = _md(category="article-presse", retraction_status="retracted")
        assert "1 rétractée(s)" in body

    def test_une_fiche_sans_aucune_source_retractable_omet_la_ligne(self):
        body = _md(category="podcast", retraction_status="unverifiable")
        assert "- Rétractation" not in body
        assert "- Accès" in body

    def test_une_fiche_sans_source_n_affiche_pas_de_bilan(self):
        from app.services.export import export_markdown

        assert "## Fiabilité des sources" not in export_markdown(_card([]), URL)


class TestVerifiabilite:
    def test_le_doi_est_present(self):
        assert "10.5555/xyz" in _md(doi="10.5555/xyz")

    def test_l_archive_est_presente(self):
        body = _md(archive_url="https://web.archive.org/web/2020/https://x.org")
        assert "web.archive.org" in body

    def test_l_acces_ouvert_est_signale(self):
        body = _md(oa_status="gold", oa_url="https://example.org/pdf")
        assert "example.org/pdf" in body

    def test_la_position_declaree_est_presente(self):
        assert "nuance" in _md(stance="nuance-contredit").lower()

    def test_une_position_non_declaree_n_est_pas_rabattue_sur_mentionne(self):
        """`None` est un silence, `mentionne` une reponse (cf. SourceStance)."""
        assert "mentionne" not in _md(stance=None).lower()

    def test_le_journal_est_present(self):
        assert "Nature Neuroscience" in _md(journal="Nature Neuroscience")


class TestRoundTrip:
    """Philum reimporte son propre markdown, et le fait imparfaitement.

    `parse_markdown` recolte toute URL du document, y compris celles qui
    decrivent une source plutot que d'en etre une : `philum_url`, l'URL du
    contenu, l'archive. Le defaut precede cette PR et n'est pas corrige ici —
    le corriger demanderait soit une liste de domaines, soit une regle sur
    l'indentation qui ferait perdre de vraies references aux bibliographies
    ecrites en listes imbriquees.

    Ecrire les metadonnees en texte plutot qu'en lien ne suffit d'ailleurs pas :
    `_DOI_RE` recolte aussi les DOI nus. Ce document est donc un format de
    *publication* qui se trouve reimportable, pas un format d'echange sans
    perte — et le dire est plus honnete que de le laisser croire.

    Ce que cette PR tient : les libelles qui ne portent ni URL ni DOI
    (retractation sans avis, revue, position declaree) n'inventent rien, et le
    DOI d'une source n'est jamais repete quand son adresse le contient deja.
    Restent deux ajouts assumes, chacun mesure ci-dessous : l'URL d'acces
    ouvert (le texte integral gratuit) et le DOI d'un avis de retractation. Les
    taire pour proteger un reimport approximatif sacrifierait l'usage principal
    au secondaire.
    """

    def test_les_libelles_sans_url_ni_doi_n_ajoutent_aucune_source(self):
        from app.services.import_parsers import parse_markdown

        nu = _md()
        enrichi = _md(
            journal="Nature",
            retraction_status="retracted",
            stance="nuance-contredit",
        )
        assert len(parse_markdown(enrichi).refs) == len(parse_markdown(nu).refs)

    def test_un_doi_deja_porte_par_l_url_n_est_pas_repete(self):
        from app.services.import_parsers import parse_markdown

        nu = _md()
        redondant = _md(url="https://doi.org/10.1234/abcd", doi="10.1234/abcd")
        assert "DOI :" not in redondant
        assert len(parse_markdown(redondant).refs) == len(parse_markdown(nu).refs)

    def test_un_doi_absent_de_l_url_est_bien_ecrit(self):
        # Le DOI est rendu dans la reference stylee (« https://doi.org/... »)
        # OU sur une ligne separee « DOI : ... » si le style ne l'a pas porte.
        # Quel que soit le style, le DOI DOIT figurer quelque part.
        body = _md(url="https://example.org/paper", doi="10.5555/xyz")
        assert "10.5555/xyz" in body

    def test_acces_ouvert_et_avis_de_retractation_ajoutent_une_entree_chacun(self):
        """Limite mesuree et assumee, pas une surprise."""
        from app.services.import_parsers import parse_markdown

        base = len(parse_markdown(_md()).refs)
        avec_oa = _md(oa_status="gold", oa_url="https://example.org/pdf")
        avec_avis = _md(retraction_status="retracted", retraction_notice_doi="10.1234/notice")
        assert len(parse_markdown(avec_oa).refs) == base + 1
        assert len(parse_markdown(avec_avis).refs) == base + 1


class TestRegressionExistant:
    """Ce que l'export garantissait deja et qui doit le rester."""

    def test_frontmatter_et_titre_de_source(self):
        body = _md()
        assert body.startswith("---\n")
        assert "tags:" in body
        assert "## Sources" in body
        assert "[Un titre de reference](https://doi.org/10.1234/abcd)" in body

    def test_une_source_sans_rien_ne_casse_pas(self):
        body = _md(title=None, authors=None, published_at=None)
        assert "https://doi.org/10.1234/abcd" in body


class TestPasDeRedondance:
    """Une meme information ecrite deux fois pour la meme source.

    Ce qui etait rendu avant chaque source, en trois lignes :
        - [Titre](URL)
          - *reference stylee (URL portee dedans)*
          - Auteurs · date · categorie · journal
          - URL
          - DOI : XXX
    Repetait l'URL/DOI jusqu'a trois fois et les auteurs deux fois. Mesure
    sur la fiche WEST-contributions-iter le 2026-08-18.
    """

    def test_url_n_est_pas_ecrite_deux_fois_hors_du_lien_markdown(self):
        url = "https://example.org/paper-unique"
        body = _md(url=url)
        # Une seule occurrence hors du `](URL)` du lien : celle de la ref
        # stylee. La ligne « URL nue » separee ne doit plus apparaitre.
        assert body.count(url) <= 2  # lien markdown + reference stylee

    def test_meta_ne_reecrit_pas_auteurs_date_journal(self):
        # Ces trois informations sont deja dans la reference stylee.
        body = _md(authors="Dupont, M.", journal="Nature")
        # Ligne meta = « - Categorie : article-scientifique » : rien d'autre.
        assert "- Catégorie : article-scientifique" in body
        # L'ancienne ligne « auteurs · date · categorie · journal » ne doit
        # plus apparaitre. La reference stylee, elle, porte les auteurs.
        assert "Dupont, M. · " not in body

    def test_doi_deja_dans_la_reference_stylee_n_est_pas_repete(self):
        # Reference stylee APA : « ... https://doi.org/10.5555/xyz ». Ecrire
        # « DOI : 10.5555/xyz » en dessous serait un doublon.
        body = _md(url="https://example.org/paper", doi="10.5555/xyz")
        # Le DOI reste visible quelque part (dans la reference stylee).
        assert "10.5555/xyz" in body
        # Mais il n'apparait pas DEUX fois : la ligne « DOI : XXX » est
        # supprimee quand la reference stylee le porte deja.
        assert body.count("10.5555/xyz") == 1


class TestDeuxVoix:
    """Ce que la source dit, et ce que le createur en dit.

    Les deux se rendaient d'abord a l'identique (`- > texte`). Attribuer a un
    auteur une phrase ecrite par le createur de la fiche serait exactement la
    faute que Philum existe pour rendre impossible : les deux voix portent donc
    chacune son nom.
    """

    def test_annotation_et_extrait_ne_se_confondent_pas(self):
        extrait = SimpleNamespace(
            position=0,
            title=None,
            text="Ce que la source dit.",
            context=None,
            suggested_by_ai=False,
            annotated_by_ai=False,
            verified_at=None,
            verified_status=None,
            verified_text_source=None,
            anchor_prefix=None,
            anchor_suffix=None,
            anchor_offset=None,
        )
        body = _md(annotation="Ce que le createur en dit.", excerpts=[extrait])
        assert "**Note du créateur** — Ce que le createur en dit." in body
        assert "**Extrait** — « Ce que la source dit. »" in body
