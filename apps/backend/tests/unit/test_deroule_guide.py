"""Le deroule guide d'une fiche sujet, tenu par le serveur.

Mesure du 2026-09-13 : laisse libre, l'agent repondait de memoire et
n'appelait jamais les outils de deroule.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.services import deroule_guide
from app.services.deroule_guide import ETAPES, est_demande_de_fiche


@pytest.mark.parametrize(
    ("message", "premier"),
    [
        ("comment prévenir l'arthrose?", True),
        ("Fait une fiche pour répondre à la question : comment prévenir l'arthrose ?", False),
        ("Crée une fiche sur l'effet Warburg", False),
        ("Pourquoi le ciel est-il bleu ?", True),
    ],
)
def test_une_demande_de_fiche_est_reconnue(message, premier):
    assert est_demande_de_fiche(message, premier_message=premier)


@pytest.mark.parametrize(
    ("message", "premier"),
    [
        ("comment prévenir l'arthrose?", False),
        ("Comment je publie ma fiche ?", True),
        ("Crée une fiche pour cette vidéo : https://youtu.be/abc", True),
        ("Merci, c'est parfait.", True),
        ("Quelle clé dois-je utiliser ?", True),
    ],
)
def test_le_reste_reste_une_conversation_libre(message, premier):
    assert not est_demande_de_fiche(message, premier_message=premier)


def _outil(nom: str, resultat: dict) -> AgentTool:
    async def execute(ctx: ToolContext, args: dict) -> dict:
        return resultat

    return AgentTool(
        name=nom,
        description=nom,
        parameters={"type": "object", "properties": {}, "required": []},
        output="dict",
        execute=execute,
    )


def _texte(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}], "usage": {}}


def _appel(nom: str, arguments: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{nom}",
                            "type": "function",
                            "function": {"name": nom, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ],
        "usage": {},
    }


async def _derouler(db_session, test_user, reponses: list[dict]):
    cle = KeyManager(get_settings().master_encryption_key).encrypt_private_key("sk-test-12345678")
    provider = AgentProvider(
        creator_id=test_user.id,
        provider="openai",
        display_name="openai",
        base_url="https://api.openai.com",
        model="gpt-4o",
        api_key_enc=cle,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.commit()
    suite = iter(reponses)
    corps: list[dict] = []

    def handler(request):
        corps.append(json.loads(request.content))
        return httpx.Response(200, json=next(suite))

    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def refuse(request_id, tool, args):
        return False

    registre = {
        "create_card": _outil("create_card", {"slug": "prevention-arthrose"}),
        "list_my_cards": _outil("list_my_cards", {"cards": []}),
        "get_my_card": _outil("get_my_card", {"slug": "prevention-arthrose"}),
        "add_source": _outil("add_source", {"id": "s1"}),
    }
    ajouts: list[dict] = []
    heures: list[datetime] = []
    await deroule_guide.derouler(
        db_session,
        test_user,
        provider,
        "comment prévenir l'arthrose?",
        emit,
        refuse,
        ajouts,
        heures,
        transport=httpx.MockTransport(handler),
        registre=registre,
    )
    return events, ajouts, heures, corps


@pytest.mark.asyncio
async def test_les_etapes_se_deroulent_dans_l_ordre(db_session, test_user):
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "prevention-arthrose"}),
        _texte("https://a.test : référence"),
        _texte("Source ajoutée : s1, deux extraits."),
        _texte("Position appuie posée."),
        _texte("Bilan : la source dit ceci."),
    ]
    events, ajouts, heures, corps = await _derouler(db_session, test_user, reponses)

    etapes = [e["payload"]["etape"] for e in events if e["type"] == "etape_guidee"]
    assert etapes == [e.id for e in ETAPES]
    assert [e["type"] for e in events].count("done") == 1
    assert events[-1]["type"] == "done"
    # Chaque etape ne voit que ses outils.
    noms_etape_1 = {t["function"]["name"] for t in corps[0]["tools"]}
    assert noms_etape_1 <= set(ETAPES[0].outils)
    assert "add_excerpt" not in noms_etape_1
    # La fiche creee est donnee aux etapes suivantes.
    consigne_etape_2 = next(m for m in corps[2]["messages"] if m["role"] == "user")["content"]
    assert "prevention-arthrose" in consigne_etape_2
    # Les numeros de tour croissent d'une etape a l'autre : la reponse finale
    # reste le texte du bilan.
    tours = [e["payload"]["tour"] for e in events if e["type"] == "message_delta"]
    assert tours == sorted(tours)
    assert [m for m in ajouts if m.get("role") == "assistant"][-1][
        "content"
    ] == "Position appuie posée."
    assert len(heures) == len(ajouts)


@pytest.mark.asyncio
async def test_sans_fiche_le_deroule_s_arrete_apres_la_recherche(db_session, test_user):
    events, ajouts, _heures, _corps = await _derouler(
        db_session, test_user, [_texte("Je n'ai rien trouvé.")]
    )
    etapes = [e["payload"]["etape"] for e in events if e["type"] == "etape_guidee"]
    assert etapes == ["recherche"]
    assert events[-1]["type"] == "error"
    assert "done" not in [e["type"] for e in events]
