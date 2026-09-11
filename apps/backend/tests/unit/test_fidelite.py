"""Le juge de fidelite : ce qu'il relit, ce qu'il declasse, ce qu'il refuse.

Les appels au fournisseur passent par `MockTransport` : aucun test ne sort sur
le reseau, et l'un d'eux verifie precisement que le juge ne l'appelle pas.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.services import fidelite


def _extrait(*, annote=True, suggere=False, verdict=None):
    return SimpleNamespace(
        id=uuid4(),
        text="Les mitochondries produisent l'ATP.",
        title=None,
        context=None,
        position=0,
        annotated_by_ai=annote,
        suggested_by_ai=suggere,
        fidelity_verdict=verdict,
        fidelity_scope=None,
        fidelity_checked_at=None,
        fidelity_note=None,
    )


def _provider():
    return SimpleNamespace(
        id=uuid4(),
        provider="openai",
        base_url="https://api.exemple.test/v1",
        model="gpt-test",
        api_key_enc="chiffre",
    )


def _user(actif=True):
    return SimpleNamespace(id=uuid4(), fidelity_judge_enabled=actif)


def _source():
    return SimpleNamespace(id=uuid4(), title="Un article", url="https://exemple.test/a")


def _transport(lignes, *, code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if code != 200:
            return httpx.Response(code, json={"error": "non"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": json.dumps(lignes)}}],
                "usage": {},
            },
        )

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _sans_dechiffrement(monkeypatch):
    monkeypatch.setattr("app.services.agent_providers._decrypt", lambda _: "cle-de-test")


def test_seuls_les_extraits_touches_par_un_modele_sont_relus():
    a_la_main = _extrait(annote=False, suggere=False)
    annote = _extrait(annote=True)
    suggere = _extrait(annote=False, suggere=True)
    cibles = fidelite.a_juger([a_la_main, annote, suggere])
    assert [e.id for e in cibles] == [annote.id, suggere.id]


@pytest.mark.asyncio
async def test_aucun_appel_quand_rien_n_a_ete_annote():
    """Le transport leve : s'il est touche, le test echoue bruyamment."""

    def handler(request):
        raise AssertionError("le juge ne doit pas appeler le fournisseur")

    rapport = await fidelite.juger(
        _user(),
        _source(),
        [_extrait(annote=False, suggere=False)],
        "un texte",
        complet=True,
        provider=_provider(),
        transport=httpx.MockTransport(handler),
    )
    assert rapport.verdicts == []
    assert rapport.erreur is None


@pytest.mark.asyncio
async def test_un_fournisseur_muet_laisse_le_verdict_nul_et_rend_une_erreur():
    extrait = _extrait()
    rapport = await fidelite.juger(
        _user(),
        _source(),
        [extrait],
        "un texte",
        complet=True,
        provider=_provider(),
        transport=_transport(None, code=503),
    )
    assert rapport.verdicts == []
    assert rapport.erreur is not None
    fidelite.appliquer([extrait], rapport)
    assert extrait.fidelity_verdict is None


@pytest.mark.asyncio
async def test_sans_cle_le_juge_le_dit_au_lieu_de_se_taire():
    rapport = await fidelite.juger(
        _user(),
        _source(),
        [_extrait()],
        "un texte",
        complet=True,
        provider=None,
    )
    assert rapport.verdicts == []
    assert "cle" in (rapport.erreur or "").lower()


def test_un_verdict_positif_sans_texte_est_declasse():
    retenu, motif = fidelite.declasser("soutient", "metadonnees_seules")
    assert retenu == "preuve_insuffisante"
    assert motif


def test_un_verdict_negatif_sans_texte_survit():
    """Un desaccord vaut quelque chose, un accord non etaye ne vaut rien."""
    for verdict in ("contredit", "mixte"):
        retenu, motif = fidelite.declasser(verdict, "metadonnees_seules")
        assert retenu == verdict
        assert motif is None


def test_avec_le_texte_aucun_verdict_n_est_declasse():
    for verdict in sorted(fidelite.VERDICTS):
        assert fidelite.declasser(verdict, "texte_integral") == (verdict, None)


@pytest.mark.asyncio
async def test_une_valeur_hors_enumeration_est_rejetee_pas_normalisee():
    extrait = _extrait()
    rapport = await fidelite.juger(
        _user(),
        _source(),
        [extrait],
        "Les mitochondries produisent l'ATP.",
        complet=True,
        provider=_provider(),
        transport=_transport([{"n": 1, "verdict": "plutot favorable", "motif": "bof"}]),
    )
    assert rapport.verdicts == []
    fidelite.appliquer([extrait], rapport)
    assert extrait.fidelity_verdict is None


@pytest.mark.asyncio
async def test_un_verdict_valide_se_pose_avec_sa_portee():
    extrait = _extrait()
    rapport = await fidelite.juger(
        _user(),
        _source(),
        [extrait],
        "Les mitochondries produisent l'ATP.",
        complet=True,
        provider=_provider(),
        transport=_transport([{"n": 1, "verdict": "soutient", "motif": "le passage le dit"}]),
    )
    assert fidelite.appliquer([extrait], rapport) == 1
    assert extrait.fidelity_verdict == "soutient"
    assert extrait.fidelity_scope == "texte_integral"
    assert extrait.fidelity_checked_at is not None
    assert extrait.fidelity_note == "le passage le dit"


@pytest.mark.asyncio
async def test_le_juge_eteint_ne_rend_aucun_verdict():
    rapport = await fidelite.juger(
        _user(actif=False),
        _source(),
        [_extrait()],
        "un texte",
        complet=True,
        provider=_provider(),
        transport=_transport([{"n": 1, "verdict": "soutient", "motif": "x"}]),
    )
    assert rapport.verdicts == []
    assert rapport.erreur is None


def test_la_portee_se_deduit_de_ce_qui_a_ete_lu():
    assert fidelite.portee_pour("", True) == "metadonnees_seules"
    assert fidelite.portee_pour("   ", False) == "metadonnees_seules"
    assert fidelite.portee_pour("du texte", True) == "texte_integral"
    assert fidelite.portee_pour("du texte", False) == "resume_seul"


def test_en_attente_ne_compte_que_ce_qu_un_modele_a_touche():
    assert (
        fidelite.en_attente(
            [
                _extrait(annote=False, suggere=False),
                _extrait(verdict=None),
                _extrait(verdict="soutient"),
            ]
        )
        == 1
    )


def test_le_rapport_porte_toujours_l_avertissement_de_non_mesure():
    assert fidelite.Rapport([]).avertissement == fidelite.AVERTISSEMENT_NON_MESURE
    assert "mesure" in fidelite.AVERTISSEMENT_NON_MESURE


def test_aucun_champ_numerique_dans_le_vocabulaire():
    """Un scalaire invite a la moyenne, et une moyenne de categories ne dit rien."""
    assert {
        "soutient",
        "contredit",
        "mixte",
        "ne_traite_pas",
        "preuve_insuffisante",
        "ambigu",
    } == fidelite.VERDICTS
    assert {"texte_integral", "resume_seul", "metadonnees_seules"} == fidelite.PORTEES
