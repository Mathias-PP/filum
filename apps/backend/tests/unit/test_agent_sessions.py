"""Tests des sessions de chat de l'agent et du registre d'approbations."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.services import agent_approvals, agent_sessions


class TestTitre:
    def test_message_court_devient_le_titre(self):
        assert agent_sessions.titre_depuis_message("Crée une fiche") == "Crée une fiche"

    def test_espaces_normalises(self):
        assert agent_sessions.titre_depuis_message("  deux   mots \n") == "deux mots"

    def test_message_vide_a_un_titre_par_defaut(self):
        assert agent_sessions.titre_depuis_message("   ") == "Nouvelle conversation"

    def test_message_long_coupe_sur_un_mot(self):
        titre = agent_sessions.titre_depuis_message("mot " * 60)
        assert len(titre) <= agent_sessions.TITRE_MAX + 1
        assert titre.endswith("…")
        assert not titre.startswith(" ")


@pytest.mark.asyncio
class TestSessions:
    async def test_creer_puis_lister(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id, title="Ma conversation")
        sessions = await agent_sessions.lister(db_session, test_user.id)
        assert [s.id for s in sessions] == [session.id]
        assert sessions[0].title == "Ma conversation"

    async def test_titre_vide_remplace_par_un_defaut(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        assert session.title == "Nouvelle conversation"

    async def test_session_dun_autre_createur_est_introuvable(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        with pytest.raises(agent_sessions.AgentSessionNotFoundError):
            await agent_sessions.obtenir(db_session, uuid4(), session.id)

    async def test_supprimee_sort_des_listes(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        await agent_sessions.supprimer(db_session, test_user.id, session.id)
        assert await agent_sessions.lister(db_session, test_user.id) == []
        with pytest.raises(agent_sessions.AgentSessionNotFoundError):
            await agent_sessions.obtenir(db_session, test_user.id, session.id)

    async def test_ajouter_message_date_la_session(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        assert session.last_message_at is None
        await agent_sessions.ajouter_message(db_session, session, role="user", content="salut")
        assert session.last_message_at is not None

    async def test_historique_rend_la_forme_du_provider(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        appels = [{"id": "call_1", "function": {"name": "web_search", "arguments": "{}"}}]
        await agent_sessions.ajouter_message(db_session, session, role="user", content="cherche")
        await agent_sessions.ajouter_message(
            db_session, session, role="assistant", tool_calls=appels
        )
        await agent_sessions.ajouter_message(
            db_session, session, role="tool", content="{}", tool_name="web_search"
        )
        await agent_sessions.ajouter_message(db_session, session, role="assistant", content="voilà")

        historique = await agent_sessions.historique_pour_modele(
            db_session, test_user.id, session.id
        )
        assert historique == [
            {"role": "user", "content": "cherche"},
            {"role": "assistant", "content": None, "tool_calls": appels},
            {"role": "tool", "name": "web_search", "content": "{}"},
            {"role": "assistant", "content": "voilà"},
        ]


@pytest.mark.asyncio
class TestApprobations:
    async def test_resoudre_debloque_lattente(self):
        request_id = str(uuid4())
        createur = uuid4()

        async def repondre():
            # Laisse `attendre` enregistrer son `Future` avant de répondre.
            await asyncio.sleep(0)
            agent_approvals.resoudre(request_id, createur, True)

        attente = asyncio.create_task(agent_approvals.attendre(request_id, createur))
        await repondre()
        assert await attente is True

    async def test_un_autre_createur_ne_peut_pas_approuver(self):
        request_id = str(uuid4())
        createur = uuid4()
        attente = asyncio.create_task(agent_approvals.attendre(request_id, createur, delai=0.2))
        await asyncio.sleep(0)
        with pytest.raises(agent_approvals.ApprovalInconnueError):
            agent_approvals.resoudre(request_id, uuid4(), True)
        # La demande reste en attente et expire donc en refus.
        assert await attente is False

    async def test_identifiant_inconnu_leve(self):
        with pytest.raises(agent_approvals.ApprovalInconnueError):
            agent_approvals.resoudre(str(uuid4()), uuid4(), True)

    async def test_delai_depasse_vaut_refus(self):
        assert await agent_approvals.attendre(str(uuid4()), uuid4(), delai=0.05) is False

    async def test_lattente_ne_laisse_rien_derriere(self):
        request_id = str(uuid4())
        await agent_approvals.attendre(request_id, uuid4(), delai=0.05)
        assert request_id not in agent_approvals._EN_ATTENTE


def _systeme(taille: int = 40) -> dict:
    return {"role": "system", "content": "S" * taille}


def _user(n: int, taille: int = 400) -> dict:
    return {"role": "user", "content": f"{n}:" + "u" * taille}


def _paire_outil(n: int, taille: int = 400) -> list[dict]:
    """Un assistant qui appelle un outil, suivi de la reponse de l'outil."""
    return [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{n}",
                    "type": "function",
                    "function": {"name": "list_my_cards", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": f"call_{n}",
            "name": "list_my_cards",
            "content": "r" * taille,
        },
    ]


class TestCompaction:
    def test_historique_sous_le_budget_reste_intact(self):
        messages = [_systeme(), _user(1), {"role": "assistant", "content": "ok"}]
        compacte, retires = agent_sessions.compacter(messages, 10_000)
        assert retires == 0
        assert compacte is messages

    def test_les_plus_anciens_partent_en_premier(self):
        messages = [_systeme(), *[_user(i) for i in range(1, 21)]]
        compacte, retires = agent_sessions.compacter(messages, 400)
        assert retires > 0
        # Le dernier message survit toujours, le premier du corps disparait.
        assert compacte[-1] == messages[-1]
        assert messages[1] not in compacte
        assert agent_sessions.taille_historique(compacte) <= 400

    def test_le_prompt_systeme_de_tete_est_conserve(self):
        systeme = _systeme(2_000)
        messages = [systeme, *[_user(i) for i in range(1, 21)]]
        compacte, retires = agent_sessions.compacter(messages, 700)
        assert retires > 0
        assert compacte[0] is systeme

    def test_une_paire_assistant_outil_n_est_jamais_separee(self):
        messages = [_systeme()]
        for i in range(1, 11):
            messages.extend(_paire_outil(i))
        compacte, retires = agent_sessions.compacter(messages, 500)
        assert retires > 0
        corps = [m for m in compacte if m.get("role") in ("assistant", "tool")]
        ids_assistant = {tc["id"] for m in corps if m.get("tool_calls") for tc in m["tool_calls"]}
        ids_tool = {m["tool_call_id"] for m in corps if m.get("role") == "tool"}
        assert ids_tool <= ids_assistant, "un message tool a survecu sans son assistant"

    def test_un_message_de_synthese_remplace_le_troncon(self):
        messages = [_systeme(), *[_user(i) for i in range(1, 21)]]
        compacte, retires = agent_sessions.compacter(messages, 400)
        synthese = compacte[1]
        assert synthese["role"] == "system"
        assert str(retires) in synthese["content"]
        assert "demandez-le au créateur" in synthese["content"]

    def test_le_dernier_bloc_survit_meme_seul_trop_gros(self):
        messages = [_systeme(), _user(1), _user(2, taille=40_000)]
        compacte, retires = agent_sessions.compacter(messages, 100)
        assert retires == 1
        assert compacte[-1] == messages[-1]

    def test_un_corps_d_un_seul_bloc_n_est_pas_coupe(self):
        messages = [_systeme(), _user(1, taille=40_000)]
        compacte, retires = agent_sessions.compacter(messages, 100)
        assert retires == 0
        assert compacte is messages

    def test_les_arguments_d_outil_comptent_dans_la_taille(self):
        nu = {"role": "assistant", "content": None}
        charge = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "add_source", "arguments": "x" * 4_000},
                }
            ],
        }
        assert (
            agent_sessions.taille_historique([charge])
            > agent_sessions.taille_historique([nu]) + 900
        )
