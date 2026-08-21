"""Tests de l'orchestrateur de fiche : séquence des étages, écriture, arrêt."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.services import agent_fiche, agent_workspace


def _provider(db_session, test_user) -> AgentProvider:
    key = KeyManager(get_settings().master_encryption_key).encrypt_private_key("sk-test-12345678")
    p = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url="https://api.openai.com",
        model="gpt-4o-mini",
        api_key_enc=key,
        is_default=True,
    )
    db_session.add(p)
    return p


def _texte(contenu: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": contenu}}], "usage": {}}


def _transport_texte(reponses: list[str]) -> httpx.MockTransport:
    """Un provider qui répond en texte, une réponse par appel."""
    restantes = list(reponses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_texte(restantes.pop(0) if restantes else "fini"))

    return httpx.MockTransport(handler)


def _registre_vide() -> dict[str, AgentTool]:
    async def _execute(ctx: ToolContext, args: dict) -> dict:
        return {"ok": True}

    return {
        "noop": AgentTool(
            name="noop",
            description="noop",
            parameters={"type": "object", "properties": {}, "required": []},
            output="dict",
            execute=_execute,
        )
    }


async def _seeder_stages(db_session, creator_id) -> None:
    for etape in agent_fiche.ETAPES:
        await agent_workspace.ecrire(
            db_session, creator_id, etape.instructions, f"Règles de {etape.id}."
        )
    await db_session.commit()


async def _lancer(db_session, test_user, provider, transport, **kwargs) -> list[dict]:
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def approuver(request_id, tool, args):
        return False

    await agent_fiche.lancer(
        db_session,
        test_user,
        provider,
        slug="ma-fiche",
        content_url="https://exemple.test/video",
        emit=emit,
        approuver=approuver,
        transport=transport,
        registre=_registre_vide(),
        **kwargs,
    )
    return events


class TestEtapes:
    def test_les_sept_etages_dans_l_ordre(self):
        assert [e.id for e in agent_fiche.ETAPES] == [
            "01-brief",
            "02-sources-collectees",
            "03-annotations",
            "04-extraits",
            "05-connexions",
            "06-relecture",
            "07-publication",
        ]

    def test_les_regles_viennent_du_workspace(self):
        assert agent_fiche.ETAPES[0].instructions == "stages/01-brief/CONTEXT.md"


@pytest.mark.asyncio
class TestLancer:
    async def test_deroule_les_etages_et_ecrit_les_comptes_rendus(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)
        transport = _transport_texte([f"rendu {e.id}" for e in agent_fiche.ETAPES])

        events = await _lancer(db_session, test_user, provider, transport)

        debuts = [e["payload"]["stage"] for e in events if e["type"] == "stage_start"]
        assert debuts == [e.id for e in agent_fiche.ETAPES]
        assert events[-1] == {
            "type": "done",
            "payload": {"reason": "fiche_complete", "slug": "ma-fiche"},
        }
        brief = await agent_workspace.lire(db_session, test_user.id, "runs/ma-fiche/00-brief.md")
        assert brief is not None
        assert brief.content == "rendu 01-brief"

    async def test_un_seul_done_pour_tout_le_run(self, db_session, test_user):
        """La boucle dit `done` par étage ; le client n'en voit qu'un."""
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)
        transport = _transport_texte(["rendu"] * len(agent_fiche.ETAPES))

        events = await _lancer(db_session, test_user, provider, transport)

        assert len([e for e in events if e["type"] == "done"]) == 1

    async def test_chaque_evenement_porte_son_etage(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)
        transport = _transport_texte(["rendu"] * len(agent_fiche.ETAPES))

        events = await _lancer(db_session, test_user, provider, transport)

        deltas = [e for e in events if e["type"] == "message_delta"]
        assert deltas
        assert deltas[0]["stage"] == "01-brief"

    async def test_un_etage_rate_arrete_le_run(self, db_session, test_user):
        """Continuer produirait des extraits accrochés à des sources absentes."""
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "clé refusée"})

        events = await _lancer(db_session, test_user, provider, httpx.MockTransport(handler))

        assert [e["payload"]["stage"] for e in events if e["type"] == "stage_failed"] == [
            "01-brief"
        ]
        assert not [e for e in events if e["type"] == "done"]
        assert (
            await agent_workspace.lire(db_session, test_user.id, "runs/ma-fiche/01-sources.md")
            is None
        )

    async def test_regles_manquantes_refuse_de_demarrer(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await db_session.commit()

        with pytest.raises(agent_fiche.FicheError, match="01-brief"):
            await _lancer(db_session, test_user, provider, _transport_texte(["x"]))

    async def test_reprise_relit_les_comptes_rendus_deja_ecrits(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)
        await agent_workspace.ecrire(
            db_session, test_user.id, "runs/ma-fiche/00-brief.md", "un brief déjà fait"
        )
        await db_session.commit()

        vus: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            vus.append(json.loads(request.content)["messages"][-1]["content"])
            return httpx.Response(200, json=_texte("rendu"))

        events = await _lancer(
            db_session,
            test_user,
            provider,
            httpx.MockTransport(handler),
            depuis="02-sources-collectees",
        )

        debuts = [e["payload"]["stage"] for e in events if e["type"] == "stage_start"]
        assert debuts[0] == "02-sources-collectees"
        assert "01-brief" not in debuts
        assert "un brief déjà fait" in vus[0]

    async def test_reprise_sur_un_etage_inconnu_refuse(self, db_session, test_user):
        provider = _provider(db_session, test_user)
        await _seeder_stages(db_session, test_user.id)

        with pytest.raises(agent_fiche.FicheError, match="Étage inconnu"):
            await _lancer(
                db_session, test_user, provider, _transport_texte(["x"]), depuis="99-inexistant"
            )


@pytest.mark.asyncio
class TestEtat:
    async def test_run_absent(self, db_session, test_user):
        etat = await agent_fiche.etat(db_session, test_user.id, "jamais-lancee")
        assert etat["demarre"] is False
        assert all(e["fait"] is False for e in etat["etapes"])

    async def test_marque_les_etages_faits(self, db_session, test_user):
        await agent_workspace.ecrire(
            db_session, test_user.id, "runs/ma-fiche/00-brief.md", "le brief"
        )
        await db_session.commit()

        etat = await agent_fiche.etat(db_session, test_user.id, "ma-fiche")

        assert etat["demarre"] is True
        faits = [e["id"] for e in etat["etapes"] if e["fait"]]
        assert faits == ["01-brief"]

    async def test_le_run_d_un_autre_createur_est_invisible(self, db_session, test_user):
        await agent_workspace.ecrire(
            db_session, test_user.id, "runs/ma-fiche/00-brief.md", "le brief"
        )
        await db_session.commit()

        etat = await agent_fiche.etat(db_session, uuid4(), "ma-fiche")

        assert etat["demarre"] is False
