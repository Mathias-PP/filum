"""Exécution des outils d'un tour : budget par outil, lectures en parallèle.

Deux défauts d'un même endroit. `_executer_tour` déroulait les appels d'outils
dans une boucle `for` séquentielle, sous le seul `BOUCLE_TIMEOUT` global de
300 s : cinq lectures de sources s'enchaînaient au lieu de partir ensemble, et
un seul `fetch_url` lent consommait le budget de tout le tour, coupant les
appels suivants qui n'avaient rien demandé.

Le parallélisme s'arrête à deux frontières, et les tests les tiennent : une
approbation est une interaction humaine, la mettre en concurrence ferait
apparaître plusieurs demandes à l'écran en même temps ; une écriture partage
l'`AsyncSession` du contexte, et ce dépôt interdit de la partager entre
coroutines.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from types import SimpleNamespace

import pytest

from app.agent_tools.tool import AgentTool, ToolContext
from app.services import agent as agent_svc


def _tc(name: str, tool_id: str, arguments: dict | None = None) -> dict:
    return {
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments or {})},
    }


def _outil(name: str, execute) -> AgentTool:
    return AgentTool(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}, "required": []},
        output="dict",
        execute=execute,
    )


def _registre_lent(noms: list[str], duree: float) -> dict[str, AgentTool]:
    async def _execute(ctx: ToolContext, args: dict) -> dict:
        await asyncio.sleep(duree)
        return {"ok": True}

    return {nom: _outil(nom, _execute) for nom in noms}


async def _lancer(registre, tool_calls, *, approuver=None):
    """Joue un tour d'outils et rend (événements, messages ajoutés)."""
    evenements: list[dict] = []
    messages: list[dict] = []

    async def emit(event):
        evenements.append(event)

    async def _accepte(request_id, tool, args):
        return True

    # La base n'est jamais touchee : les outils sont faux et le resume
    # d'approbation retombe sur son libelle generique quand il echoue.
    await agent_svc._executer_tour(
        None,
        SimpleNamespace(id=uuid.uuid4()),
        1,
        messages,
        tool_calls,
        registre,
        emit,
        approuver or _accepte,
    )
    return evenements, messages


class TestBudgetParOutil:
    async def test_un_outil_qui_depasse_rend_une_erreur_nommee(self, monkeypatch):
        monkeypatch.setattr(agent_svc, "TIMEOUT_OUTIL", 0.05)
        registre = _registre_lent(["get_card"], 0.5)
        _, messages = await _lancer(registre, [_tc("get_card", "a")])
        assert "get_card" in messages[0]["content"]
        assert "n'a pas répondu" in messages[0]["content"]

    async def test_le_depassement_d_un_outil_ne_coupe_pas_les_autres(self, monkeypatch):
        monkeypatch.setattr(agent_svc, "TIMEOUT_OUTIL", 0.05)
        registre = {
            **_registre_lent(["get_card"], 0.5),
            **_registre_lent(["get_source"], 0.0),
        }
        _, messages = await _lancer(registre, [_tc("get_card", "a"), _tc("get_source", "b")])
        assert len(messages) == 2
        assert "n'a pas répondu" in messages[0]["content"]
        assert "ok" in messages[1]["content"]

    def test_les_budgets_par_outil_restent_sous_le_budget_du_tour(self):
        """Un outil qui aurait le droit de manger tout le tour ne servirait
        a rien : la boucle serait coupee avant d'avoir pu lire son erreur."""
        budgets = [agent_svc.TIMEOUT_OUTIL, *agent_svc.TIMEOUTS_PAR_OUTIL.values()]
        assert max(budgets) < agent_svc.BOUCLE_TIMEOUT

    def test_les_outils_lents_ont_un_budget_plus_large(self):
        """Une lecture web est legitimement lente : lui appliquer le budget
        par defaut la ferait echouer sur des pages parfaitement saines."""
        assert agent_svc.TIMEOUTS_PAR_OUTIL["fetch_url"] > agent_svc.TIMEOUT_OUTIL


class TestParallelisme:
    async def test_trois_lectures_partent_ensemble(self):
        registre = _registre_lent(["get_card", "get_source", "search_cards"], 0.2)
        appels = [_tc("get_card", "a"), _tc("get_source", "b"), _tc("search_cards", "c")]
        debut = time.monotonic()
        await _lancer(registre, appels)
        assert time.monotonic() - debut < 0.45

    async def test_un_lot_qui_ecrit_reste_en_file(self):
        """Deux ecritures concurrentes partageraient l'`AsyncSession` du
        contexte, ce que ce depot interdit."""
        registre = _registre_lent(["get_card", "add_excerpt"], 0.2)
        appels = [_tc("get_card", "a"), _tc("add_excerpt", "b")]
        debut = time.monotonic()
        await _lancer(registre, appels)
        assert time.monotonic() - debut >= 0.4

    async def test_un_lot_qui_demande_une_approbation_reste_en_file(self):
        """Deux approbations en concurrence feraient apparaitre deux demandes
        simultanees a l'ecran, sans dire laquelle repond a quoi."""
        registre = _registre_lent(["get_card", "delete_source"], 0.2)
        appels = [_tc("get_card", "a"), _tc("delete_source", "b")]
        debut = time.monotonic()
        await _lancer(registre, appels)
        assert time.monotonic() - debut >= 0.4

    async def test_un_seul_appel_ne_change_rien(self):
        registre = _registre_lent(["get_card"], 0.0)
        _, messages = await _lancer(registre, [_tc("get_card", "a")])
        assert len(messages) == 1


class TestOrdre:
    async def test_les_messages_tool_suivent_l_ordre_des_tool_calls(self):
        """Un lot desordonne casse la correspondance chez certains
        fournisseurs : l'ordre rendu est celui demande, jamais l'ordre
        d'arrivee des resultats."""
        durees = {"get_card": 0.3, "get_source": 0.1, "search_cards": 0.2}

        def _fait(duree):
            async def _execute(ctx, args):
                await asyncio.sleep(duree)
                return {"ok": True}

            return _execute

        registre = {nom: _outil(nom, _fait(d)) for nom, d in durees.items()}
        appels = [_tc("get_card", "a"), _tc("get_source", "b"), _tc("search_cards", "c")]
        _, messages = await _lancer(registre, appels)
        assert [m["tool_call_id"] for m in messages] == ["a", "b", "c"]

    async def test_les_evenements_tool_result_suivent_le_meme_ordre(self):
        """Sinon l'interface affiche les cartes d'outil dans le desordre."""

        def _fait(duree):
            async def _execute(ctx, args):
                await asyncio.sleep(duree)
                return {"ok": True}

            return _execute

        registre = {
            nom: _outil(nom, _fait(d)) for nom, d in {"get_card": 0.3, "get_source": 0.1}.items()
        }
        evenements, _ = await _lancer(registre, [_tc("get_card", "a"), _tc("get_source", "b")])
        resultats = [e for e in evenements if e["type"] == "tool_result"]
        assert [e["payload"]["id"] for e in resultats] == ["a", "b"]

    async def test_un_appel_sans_identifiant_en_recoit_un(self):
        """Le lot entier est annonce avant le premier resultat : cote
        interface, un resultat sans identifiant rejoindrait la derniere carte
        en attente et non la sienne."""
        registre = _registre_lent(["get_card", "get_source"], 0.0)
        appels = [
            {"type": "function", "function": {"name": "get_card", "arguments": "{}"}},
            {"type": "function", "function": {"name": "get_source", "arguments": "{}"}},
        ]
        evenements, messages = await _lancer(registre, appels)
        ids_annonces = [e["payload"]["id"] for e in evenements if e["type"] == "tool_call"]
        ids_rendus = [e["payload"]["id"] for e in evenements if e["type"] == "tool_result"]
        assert all(i for i in ids_annonces)
        assert len(set(ids_annonces)) == 2
        assert ids_rendus == ids_annonces
        assert [m["tool_call_id"] for m in messages] == ids_annonces


class TestNonRegression:
    async def test_les_arguments_illisibles_restent_une_erreur_lisible(self):
        registre = _registre_lent(["get_card"], 0.0)
        appel = {
            "id": "a",
            "type": "function",
            "function": {"name": "get_card", "arguments": '{"slug": "tronq'},
        }
        _, messages = await _lancer(registre, [appel])
        assert "illisibles" in messages[0]["content"]

    async def test_un_refus_d_approbation_rend_le_refus(self):
        async def _refuse(request_id, tool, args):
            return False

        registre = _registre_lent(["delete_source"], 0.0)
        _, messages = await _lancer(registre, [_tc("delete_source", "a")], approuver=_refuse)
        assert "refusée" in messages[0]["content"]

    async def test_un_appel_sans_nom_est_ignore(self):
        registre = _registre_lent(["get_card"], 0.0)
        _, messages = await _lancer(registre, [{"id": "a", "type": "function"}])
        assert messages == []


@pytest.mark.parametrize(
    ("noms", "attendu"),
    [
        (["get_card", "get_source"], True),
        (["get_card"], False),
        (["get_card", "add_excerpt"], False),
        (["get_card", "delete_source"], False),
        (["add_excerpt", "update_card"], False),
    ],
)
def test_decision_de_parallelisation(noms, attendu):
    appels = [(_tc(n, str(i)), n, {}, True) for i, n in enumerate(noms)]
    assert agent_svc._lot_parallelisable(appels) is attendu
