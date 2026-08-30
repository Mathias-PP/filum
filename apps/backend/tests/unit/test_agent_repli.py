"""Le repli entre clés : ce qu'il tente, et ce qu'il refuse de tenter."""

from __future__ import annotations

from uuid import uuid4

from app.services.agent_repli import (
    _REPOS_INITIAL_S,
    _REPOS_MAX_S,
    Repos,
    Verdict,
    classer,
)


def test_cle_revoquee_abandonne_sans_essayer_les_autres():
    """Le verdict qui manquait, et le seul qui evite trois echecs pour un.

    Un 401 ne dit rien de la sante des autres cles : les essayer ferait payer
    deux appels de plus pour le meme resultat, et compterait un incident contre
    des cles qui n'ont rien fait.
    """
    decision = classer(401, "invalid api key")

    assert decision.verdict is Verdict.ABANDONNER
    assert "clé" in decision.raison


def test_modele_inconnu_abandonne():
    assert classer(404, "model not found").verdict is Verdict.ABANDONNER


def test_quota_replie_sur_la_cle_suivante():
    decision = classer(429, "rate limit exceeded")

    assert decision.verdict is Verdict.REPLIER
    assert "autre clé" in decision.raison


def test_solde_epuise_replie_meme_en_400():
    """Les fournisseurs ne s'accordent pas sur le code d'un solde vide."""
    assert classer(400, "insufficient balance").verdict is Verdict.REPLIER


def test_panne_du_fournisseur_fait_reessayer_la_meme_cle():
    decision = classer(503, "service unavailable")

    assert decision.verdict is Verdict.REESSAYER
    assert "ne vient pas de la clé" in decision.raison


def test_reseau_injoignable_fait_reessayer():
    assert classer(None, "connect timeout").verdict is Verdict.REESSAYER


def test_contenu_refuse_abandonne_quel_que_soit_le_statut():
    """Un refus de filtrage tient a la demande, pas au fournisseur."""
    for statut in (200, 400, 403, 429):
        assert classer(statut, "blocked by safety settings").verdict is Verdict.ABANDONNER


def test_le_repos_croit_et_plafonne_a_quinze_minutes():
    """Sans plafond, une panne de dix minutes condamnerait la clé pour des heures."""
    r = Repos()
    cle = uuid4()

    durees = [r.signaler(cle) for _ in range(12)]

    assert durees[0] == _REPOS_INITIAL_S
    assert durees[1] == _REPOS_INITIAL_S * 2
    assert durees[-1] == _REPOS_MAX_S
    assert max(durees) == _REPOS_MAX_S


def test_une_cle_signalee_est_au_repos():
    r = Repos()
    cle, autre = uuid4(), uuid4()

    r.signaler(cle)

    assert r.au_repos(cle)
    assert not r.au_repos(autre)


def test_une_reussite_efface_l_historique():
    """Sinon une clé qui tombe une fois par mois partirait au plafond."""
    r = Repos()
    cle = uuid4()
    r.signaler(cle)
    r.signaler(cle)

    r.reussite(cle)

    assert not r.au_repos(cle)
    assert r.signaler(cle) == _REPOS_INITIAL_S
