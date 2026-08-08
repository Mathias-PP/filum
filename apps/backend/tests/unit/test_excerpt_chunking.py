"""Le decoupage en extraits ne peut pas dependre du bon vouloir d'un site.

Mesure du 2026-08-08, dix URLs dont les quatre personas de l'audit : **cinq ne
rendent aucun texte exploitable** a `_html_scrape`. NYT, ScienceDirect,
treasury.gov et Cell rendent zero caractere ; YouTube 313.

Aujourd'hui `/suggest` repond `422 no_text` dans ces cas : la fonctionnalite
s'arrete a la porte, alors que la personne a le texte sous les yeux. Le repli
retenu est donc le texte qu'elle colle -- le seul qui couvre les cinq, une
capture Wayback ne rattrapant ni ScienceDirect ni Cell, dont le texte est
derriere un paywall.

D'ou la regle que ces tests tiennent : **une page illisible n'est pas une
erreur, c'est un etat**. Le serveur dit d'ou vient le texte et ce qu'il a
trouve ; l'interface bascule en collage plutot que d'afficher un echec.
"""

from __future__ import annotations

from app.api.v1.endpoints.excerpts import (
    ChunkRequest,
    decouper_pour_reponse,
)
from app.services.chunker import Unite

TEXTE = (
    "La memoire de travail retient une information le temps de s'en servir. "
    "Elle ne dure que quelques secondes. Baddeley en a propose un modele en "
    "1974.\n\n"
    "Ce modele distingue trois composantes. La boucle phonologique traite le "
    "verbal. Le calepin visuo-spatial traite l'image."
)


class TestLaTailleSePropose:
    """« En cliquant simplement sur un bouton » : la taille n'est pas saisie."""

    def test_sans_taille_demandee_une_taille_est_proposee(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE))
        assert rep.suggested_size > 0
        assert rep.chunks

    def test_la_taille_demandee_prime_sur_la_suggestion(self) -> None:
        petit = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, size=60))
        gros = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, size=100_000))
        assert len(petit.chunks) > len(gros.chunks)


class TestLUniteEstAuChoix:
    def test_les_trois_unites_sont_acceptees(self) -> None:
        for unite in (Unite.CARACTERES, Unite.MOTS, Unite.TOKENS):
            rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, unit=unite))
            assert rep.chunks
            assert rep.unit == unite

    def test_chaque_morceau_porte_sa_mesure_dans_l_unite_choisie(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, unit=Unite.MOTS, size=15))
        for c in rep.chunks:
            assert c.size == len(c.text.split())


class TestLesBornesSontExploitables:
    """L'interface les rend deplacables : elles doivent designer le texte."""

    def test_les_offsets_retrouvent_le_morceau_dans_le_texte_rendu(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, size=80))
        for c in rep.chunks:
            assert rep.text[c.start : c.end] == c.text

    def test_le_texte_source_est_rendu_pour_que_les_bornes_aient_un_sens(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE))
        assert rep.text == TEXTE


class TestUnePageIllisibleEstUnEtatPasUneErreur:
    def test_un_texte_vide_ne_leve_rien_et_se_declare(self) -> None:
        """Cinq URLs sur dix : le serveur doit repondre, pas echouer."""
        rep = decouper_pour_reponse("", ChunkRequest())
        assert rep.chunks == []
        assert rep.text_source == "none"

    def test_le_texte_colle_est_annonce_comme_tel(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE))
        assert rep.text_source == "pasted"

    def test_le_texte_recupere_est_annonce_comme_tel(self) -> None:
        """Sans collage, le texte vient du site : la provenance change."""
        rep = decouper_pour_reponse(TEXTE, ChunkRequest())
        assert rep.text_source == "fetched"


class TestLeTexteNEstJamaisDeforme:
    def test_chaque_morceau_apparait_tel_quel_dans_la_source(self) -> None:
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE, size=40))
        for c in rep.chunks:
            assert c.text in TEXTE

    def test_aucun_titre_n_est_invente_par_le_decoupage(self) -> None:
        """Un intitule faux vaut moins que pas d'intitule (#317, #323, #327)."""
        rep = decouper_pour_reponse(TEXTE, ChunkRequest(text=TEXTE))
        assert all(c.title is None for c in rep.chunks)
