"""Decouper un texte en extraits proposables, sans jamais deformer le texte.

Mesure du 2026-08-08 sur dix URLs, dont les quatre personas de l'audit :
**cinq ne rendent aucun texte exploitable**. NYT, ScienceDirect, treasury.gov
et Cell rendent zero caractere ; YouTube 313. La suggestion de citations, qui
lit `page_text`, echoue donc une fois sur deux -- et sur ScienceDirect ou Cell
une capture Wayback ne rattraperait rien, le texte etant derriere un paywall.

Le seul repli qui couvre tous les cas est le texte que la personne a sous les
yeux et colle elle-meme. Ce module en fait des extraits proposables. Il ne
depend d'aucun reseau et d'aucune cle : c'est ce qui lui permet d'etre le
plancher sur lequel le reste s'appuie.

Deux exigences le gouvernent.

1. **Le texte rendu est le texte recu.** Un extrait sert a citer ; recoller
   les morceaux doit redonner l'original, aux espaces de bordure pres. Rien ne
   se reecrit, rien ne se resume.
2. **La coupe tombe ou le sens s'arrete.** Couper au milieu d'une phrase
   produit un fragment -- la meme faute que le titre pris sur le texte d'un
   lien (#327). La taille demandee est donc une cible, pas un couperet.
"""

from __future__ import annotations

import pytest

from app.services.chunker import Unite, chunk_text, compter, suggerer_taille

TEXTE = (
    "La memoire de travail retient une information le temps de s'en servir. "
    "Elle ne dure que quelques secondes. Baddeley en a propose un modele en "
    "1974.\n\n"
    "Ce modele distingue trois composantes. La boucle phonologique traite le "
    "verbal. Le calepin visuo-spatial traite l'image. L'administrateur central "
    "arbitre entre les deux."
)


class TestLeTexteRenduEstLeTexteRecu:
    """Un extrait sert a citer : il ne peut pas s'ecarter de l'original."""

    def test_recoller_les_morceaux_redonne_l_original(self) -> None:
        morceaux = chunk_text(TEXTE, taille=80, unite=Unite.CARACTERES)
        recolle = " ".join(m.text for m in morceaux)
        assert "".join(recolle.split()) == "".join(TEXTE.split())

    def test_chaque_morceau_apparait_tel_quel_dans_l_original(self) -> None:
        for m in chunk_text(TEXTE, taille=60, unite=Unite.MOTS):
            assert m.text in TEXTE

    def test_les_offsets_designent_le_morceau(self) -> None:
        """Le frontend deplace des bornes : elles doivent viser juste."""
        for m in chunk_text(TEXTE, taille=100, unite=Unite.CARACTERES):
            assert TEXTE[m.start : m.end] == m.text

    def test_aucun_morceau_vide(self) -> None:
        assert all(m.text.strip() for m in chunk_text(TEXTE, taille=20, unite=Unite.CARACTERES))


class TestLaCoupeTombeOuLeSensSArrete:
    def test_un_morceau_ne_finit_pas_au_milieu_d_une_phrase(self) -> None:
        morceaux = chunk_text(TEXTE, taille=120, unite=Unite.CARACTERES)
        for m in morceaux[:-1]:
            assert m.text.rstrip()[-1] in ".!?…»"

    def test_une_phrase_plus_longue_que_la_cible_n_est_pas_coupee(self) -> None:
        """La cible est une cible : mieux vaut un morceau long qu'un fragment."""
        phrase = "Un " + "tres " * 60 + "long enonce sans aucune ponctuation interne."
        morceaux = chunk_text(phrase, taille=50, unite=Unite.CARACTERES)
        assert len(morceaux) == 1
        assert morceaux[0].text == phrase.strip()

    def test_un_saut_de_paragraphe_est_toujours_une_coupe(self) -> None:
        morceaux = chunk_text(TEXTE, taille=10_000, unite=Unite.CARACTERES)
        assert len(morceaux) == 2

    def test_un_texte_vide_ne_donne_aucun_morceau(self) -> None:
        assert chunk_text("   \n\n  ", taille=100, unite=Unite.CARACTERES) == []


class TestLUniteDeMesure:
    """Caracteres, mots ou tokens : l'auteur·ice choisit ce qui lui parle."""

    @pytest.mark.parametrize(
        ("unite", "attendu"),
        [(Unite.CARACTERES, 11), (Unite.MOTS, 2), (Unite.TOKENS, 3)],
    )
    def test_compter_suit_l_unite(self, unite: Unite, attendu: int) -> None:
        assert compter("Bonjour toi", unite) == attendu

    def test_le_token_est_une_approximation_assumee(self) -> None:
        """~4 caracteres par token : l'ordre de grandeur, sans dependance."""
        texte = "x" * 400
        assert 80 <= compter(texte, Unite.TOKENS) <= 120

    def test_la_taille_demandee_est_a_peu_pres_tenue(self) -> None:
        morceaux = chunk_text(TEXTE, taille=25, unite=Unite.MOTS)
        assert all(compter(m.text, Unite.MOTS) <= 60 for m in morceaux)


class TestLaSuggestionDeTaille:
    """« Un bouton » : la taille se propose, l'auteur·ice la corrige ensuite."""

    def test_un_texte_court_donne_une_cible_plus_petite_qu_un_long(self) -> None:
        court = suggerer_taille("Deux phrases courtes. Rien de plus.", Unite.CARACTERES)
        long = suggerer_taille(TEXTE * 40, Unite.CARACTERES)
        assert court < long

    def test_la_cible_suggeree_est_utilisable_telle_quelle(self) -> None:
        taille = suggerer_taille(TEXTE, Unite.CARACTERES)
        morceaux = chunk_text(TEXTE, taille=taille, unite=Unite.CARACTERES)
        assert 1 <= len(morceaux) <= 10

    def test_la_cible_suit_l_unite_demandee(self) -> None:
        """Une cible en mots ne peut pas valoir une cible en caracteres."""
        assert suggerer_taille(TEXTE, Unite.MOTS) < suggerer_taille(TEXTE, Unite.CARACTERES)

    def test_un_texte_vide_ne_fait_pas_tomber_la_suggestion(self) -> None:
        assert suggerer_taille("", Unite.CARACTERES) > 0
