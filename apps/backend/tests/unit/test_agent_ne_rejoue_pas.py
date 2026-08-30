"""Un appel qui a déjà échoué à l'identique n'est pas rejoué.

Mesure du 2026-08-30, sur une session réelle en production (ministral 8b, fiche
sur l'effet Warburg). La source était illisible, `add_excerpt` a refusé, et le
modèle a rejoué le même appel mot pour mot six fois de suite avant d'abandonner
et de proposer à la personne de coller le passage elle-même.

La règle 5 du prompt système interdit déjà de répéter un appel identique après
une erreur. Elle n'a pas tenu, et c'est attendu : une consigne se contourne en
l'ignorant. Le rejeu est donc rendu impossible dans la couche outil, où le
modèle n'a pas voix au chapitre.

Ce que ces tests fixent, au-delà du fait que la boucle casse : ce qui compte
comme « le même » appel, ce qui est mémorisé, et ce qui ne l'est surtout pas.
Un succès se rejoue (rien ne dit qu'un outil soit idempotent, mais rien
n'autorise non plus à décider à sa place), et un refus d'approbation ne se
mémorise pas, sinon dire « non » une fois interdirait de dire « oui » ensuite.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

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


def _registre(nom: str, reponse: dict, compteur: list[int]) -> dict[str, AgentTool]:
    """Un outil qui rend toujours la même chose et compte ses exécutions."""

    async def _execute(ctx: ToolContext, args: dict) -> dict:
        compteur.append(1)
        return reponse

    return {nom: _outil(nom, _execute)}


async def _lancer(registre, tool_calls, *, echecs=None, approuver=None):
    """Joue un tour d'outils et rend les messages ajoutés."""
    messages: list[dict] = []

    async def emit(event):
        return None

    async def _accepte(request_id, tool, args):
        return True

    await agent_svc._executer_tour(
        None,
        SimpleNamespace(id=uuid.uuid4()),
        1,
        messages,
        tool_calls,
        registre,
        emit,
        approuver or _accepte,
        None,
        echecs,
    )
    return messages


class TestUnEchecNeSeRejouePas:
    async def test_le_second_appel_identique_n_atteint_pas_l_outil(self):
        """Le cœur du correctif : la boucle de six devient une boucle de une."""
        faits: list[int] = []
        registre = _registre("add_excerpt", {"error": "Source illisible."}, faits)
        echecs: dict[str, str] = {}

        await _lancer(registre, [_tc("add_excerpt", "a", {"text": "x"})], echecs=echecs)
        messages = await _lancer(registre, [_tc("add_excerpt", "b", {"text": "x"})], echecs=echecs)

        assert len(faits) == 1
        assert "déjà fait cet appel" in messages[0]["content"]

    async def test_le_refus_rappelle_ce_qu_avait_dit_l_erreur(self):
        """Sans la cause, le modèle ne peut que deviner quoi changer."""
        faits: list[int] = []
        registre = _registre("add_excerpt", {"error": "Le texte est absent de la source."}, faits)
        echecs: dict[str, str] = {}

        await _lancer(registre, [_tc("add_excerpt", "a", {"text": "x"})], echecs=echecs)
        messages = await _lancer(registre, [_tc("add_excerpt", "b", {"text": "x"})], echecs=echecs)

        assert "déjà fait cet appel" in messages[0]["content"]
        assert "Le texte est absent de la source." in messages[0]["content"]

    async def test_la_memoire_enjambe_les_tours(self):
        """La répétition observée n'était pas dans un tour : le modèle relisait
        l'erreur, puis refaisait le même appel au tour suivant. Une mémoire de
        la durée d'un tour n'aurait rien attrapé."""
        faits: list[int] = []
        registre = _registre("add_excerpt", {"error": "Source illisible."}, faits)
        echecs: dict[str, str] = {}

        for identifiant in ("a", "b", "c", "d", "e", "f"):
            await _lancer(registre, [_tc("add_excerpt", identifiant, {"text": "x"})], echecs=echecs)

        assert len(faits) == 1


class TestCeQuiResteAutorise:
    async def test_un_appel_qui_a_reussi_se_rejoue(self):
        """Seuls les échecs sont mémorisés. Ajouter deux extraits identiques
        est peut-être une erreur du modèle, mais ce n'est pas à cette couche
        d'en décider, et rien ne dit qu'un outil soit idempotent."""
        faits: list[int] = []
        registre = _registre("add_excerpt", {"ok": True}, faits)
        echecs: dict[str, str] = {}

        await _lancer(registre, [_tc("add_excerpt", "a", {"text": "x"})], echecs=echecs)
        await _lancer(registre, [_tc("add_excerpt", "b", {"text": "x"})], echecs=echecs)

        assert len(faits) == 2

    async def test_des_arguments_differents_ne_sont_pas_bloques(self):
        """Corriger ses arguments après une erreur est exactement ce qu'on
        attend : le garde-fou ne doit pas interdire la sortie de boucle."""
        faits: list[int] = []
        registre = _registre("add_excerpt", {"error": "Source illisible."}, faits)
        echecs: dict[str, str] = {}

        await _lancer(registre, [_tc("add_excerpt", "a", {"text": "x"})], echecs=echecs)
        await _lancer(registre, [_tc("add_excerpt", "b", {"text": "y"})], echecs=echecs)

        assert len(faits) == 2

    async def test_le_meme_argument_sur_un_autre_outil_n_est_pas_bloque(self):
        faits_un: list[int] = []
        faits_deux: list[int] = []
        registre = {
            **_registre("add_excerpt", {"error": "Source illisible."}, faits_un),
            **_registre("update_excerpt", {"error": "Source illisible."}, faits_deux),
        }
        echecs: dict[str, str] = {}

        await _lancer(registre, [_tc("add_excerpt", "a", {"text": "x"})], echecs=echecs)
        await _lancer(registre, [_tc("update_excerpt", "b", {"text": "x"})], echecs=echecs)

        assert len(faits_un) == 1
        assert len(faits_deux) == 1

    async def test_un_refus_d_approbation_ne_se_memorise_pas(self):
        """La personne a le droit de refuser puis d'accepter. Mémoriser son
        refus lui retirerait ce droit, et le garde-fou se retournerait contre
        celle qu'il protège."""
        faits: list[int] = []
        registre = _registre("delete_source", {"ok": True}, faits)
        echecs: dict[str, str] = {}
        reponses = iter([False, True])

        async def _puis_accepte(request_id, tool, args):
            return next(reponses)

        appel = {"source_id": "s1"}
        await _lancer(
            registre, [_tc("delete_source", "a", appel)], echecs=echecs, approuver=_puis_accepte
        )
        await _lancer(
            registre, [_tc("delete_source", "b", appel)], echecs=echecs, approuver=_puis_accepte
        )

        assert len(faits) == 1
        assert echecs == {}


class TestEmpreinte:
    def test_l_ordre_des_cles_ne_change_pas_l_empreinte(self):
        """Un fournisseur ne garantit pas l'ordre des champs d'un objet JSON :
        deux sérialisations du même appel doivent se reconnaître, sinon le
        garde-fou laisse passer la boucle qu'il est là pour casser."""
        un = agent_svc._empreinte("add_excerpt", {"text": "x", "source_id": "s"})
        deux = agent_svc._empreinte("add_excerpt", {"source_id": "s", "text": "x"})
        assert un == deux

    def test_des_valeurs_differentes_donnent_des_empreintes_differentes(self):
        un = agent_svc._empreinte("add_excerpt", {"text": "x"})
        deux = agent_svc._empreinte("add_excerpt", {"text": "y"})
        assert un != deux

    def test_le_nom_de_l_outil_fait_partie_de_l_empreinte(self):
        un = agent_svc._empreinte("add_excerpt", {"text": "x"})
        deux = agent_svc._empreinte("update_excerpt", {"text": "x"})
        assert un != deux

    def test_les_accents_ne_sont_pas_echappes(self):
        """`ensure_ascii=False` : sans lui, l'empreinte reste correcte mais
        devient illisible dans un log, où on la lira le jour d'un incident."""
        assert "é" in agent_svc._empreinte("add_excerpt", {"text": "clé"})

    def test_une_valeur_non_serialisable_ne_leve_pas(self):
        """`default=str` : un argument exotique venu d'un fournisseur ne doit
        pas faire tomber le tour entier depuis le garde-fou."""
        assert agent_svc._empreinte("add_excerpt", {"id": uuid.uuid4()})
