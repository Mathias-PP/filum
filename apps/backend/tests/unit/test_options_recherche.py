"""Le mode et les sources choisis par le créateur, et les questions du déroulé qui attendent une réponse."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.services import agent_approvals
from app.services.options_recherche import (
    CHOIX_SOURCES,
    OPTIONS_RECHERCHE,
    Options,
    filtrer_corpus,
    options_choisies,
    options_courantes,
    options_demandees,
)

CORPUS = {"openalex": 1, "europepmc": 2, "semantic_scholar": 3, "web": 4}


def test_sans_choix_tous_les_corpus_sont_interroges():
    assert filtrer_corpus(CORPUS, Options()) == CORPUS


def test_les_familles_choisies_filtrent_les_corpus():
    assert filtrer_corpus(CORPUS, Options(sources=frozenset({"web"}))) == {"web": 4}
    assert set(filtrer_corpus(CORPUS, Options(sources=frozenset({"litterature"})))) == {
        "openalex",
        "europepmc",
        "semantic_scholar",
    }


def test_sans_choix_les_publications_passent_d_abord_et_le_cadrage_peut_demander():
    defaut = options_demandees("approfondi", [], None)
    assert defaut == Options() and defaut.publications_d_abord and not defaut.sources_choisies
    assert options_demandees("approfondi", [], "egale") == Options(
        publications_d_abord=False, sources_choisies=True
    )
    assert options_demandees("rapide", ["web"], None).sources_choisies


def test_la_reponse_du_createur_devient_des_options():
    egalite, _publications, litterature = (
        list(CHOIX_SOURCES)[1],
        list(CHOIX_SOURCES)[0],
        list(CHOIX_SOURCES)[2],
    )
    assert options_choisies(Options(mode="rapide"), egalite) == Options(
        mode="rapide", publications_d_abord=False, sources_choisies=True
    )
    assert options_choisies(Options(), litterature).sources == frozenset({"litterature"})
    assert options_choisies(Options(), "Des podcasts") is None


def test_hors_chat_la_methode_est_complete():
    assert options_courantes() == Options()
    jeton = OPTIONS_RECHERCHE.set(Options(mode="rapide"))
    try:
        assert options_courantes().rapide
    finally:
        OPTIONS_RECHERCHE.reset(jeton)


@pytest.mark.asyncio
async def test_une_question_du_deroule_attend_la_reponse_de_son_createur():
    createur, autre = uuid4(), uuid4()

    async def repondre():
        await asyncio.sleep(0)
        with pytest.raises(agent_approvals.ApprovalInconnueError):
            agent_approvals.resoudre_reponse("q1", autre, {"choix": "intrus"})
        agent_approvals.resoudre_reponse("q1", createur, {"choix": "Adultes"})

    reponse, _ = await asyncio.gather(
        agent_approvals.attendre_reponse("q1", createur, delai=5), repondre()
    )
    assert reponse == {"choix": "Adultes"}


@pytest.mark.asyncio
async def test_sans_reponse_le_deroule_continue():
    assert await agent_approvals.attendre_reponse("q2", uuid4(), delai=0.01) is None
