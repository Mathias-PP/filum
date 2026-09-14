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
from app.services import deroule_guide, relecture
from app.services.couverture import Couverture, SousQuestion
from app.services.deroule_guide import ETAPES, est_demande_de_fiche, relancer_une_passe
from app.services.relecture import Manque


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


async def _derouler(db_session, test_user, reponses: list[dict], slug="prevention-arthrose"):
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
        "create_card": _outil("create_card", {"slug": slug}),
        "list_my_cards": _outil("list_my_cards", {"cards": []}),
        "get_my_card": _outil("get_my_card", {"slug": slug}),
        "definir_plan": _outil("definir_plan", {"slug": slug, "sous_questions": []}),
        "add_source": _outil("add_source", {"id": "s1"}),
        "rechercher": _outil("rechercher", {"sources": []}),
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


def _etapes(events: list[dict]) -> list[str]:
    return [e["payload"]["etape"] for e in events if e["type"] == "etape_guidee"]


@pytest.mark.asyncio
async def test_les_etapes_se_deroulent_dans_l_ordre(db_session, test_user):
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "prevention-arthrose"}),
        _texte("Fiche prevention-arthrose, plan posé."),
        _texte("Source ajoutée : s1, deux extraits."),
        _texte("Position appuie posée."),
        _texte("Bilan : la source dit ceci."),
    ]
    events, ajouts, heures, corps = await _derouler(db_session, test_user, reponses)

    assert _etapes(events) == [e.id for e in ETAPES]
    assert "recherche" not in _etapes(events)
    # Sans plan, l'exploration porte sur la question elle-meme.
    assert (
        "Sous-question travaillée : comment prévenir l'arthrose?"
        in next(m for m in corps[2]["messages"] if m["role"] == "user")["content"]
    )
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
async def test_sans_fiche_le_deroule_s_arrete_apres_le_plan(db_session, test_user):
    events, _ajouts, _heures, _corps = await _derouler(
        db_session, test_user, [_texte("Je n'ai rien trouvé.")]
    )
    assert _etapes(events) == ["plan"]
    assert events[-1]["type"] == "error"
    assert "done" not in [e["type"] for e in events]


TRANSPORT = "La taxe carbone réduit-elle les émissions du transport ?"
INDUSTRIE = "Quel effet la taxe a-t-elle eu sur l'industrie lourde ?"


def _etat(*couvertes: str) -> Couverture:
    return Couverture(
        slug="taxe-carbone",
        sous_questions=[
            SousQuestion(q, int(q in couvertes), int(q in couvertes))
            for q in (TRANSPORT, INDUSTRIE)
        ],
        sources_sans_extrait=0,
        extraits=len(couvertes),
    )


def _couvertures(monkeypatch, *etats: Couverture) -> None:
    """Rend les etats dans l'ordre des lectures, puis garde le dernier."""
    file = list(etats)

    async def calculer(db, creator_id, slug):
        return file.pop(0) if len(file) > 1 else file[0]

    monkeypatch.setattr(deroule_guide.couverture, "calculer", calculer)


def test_une_passe_est_relancee_tant_qu_elle_couvre_du_neuf():
    assert relancer_une_passe(_etat(), _etat(TRANSPORT))
    assert not relancer_une_passe(_etat(TRANSPORT), _etat(TRANSPORT))
    assert not relancer_une_passe(_etat(), _etat(TRANSPORT, INDUSTRIE))
    assert not relancer_une_passe(None, _etat())


def _consignes(corps: list[dict]) -> list[str]:
    return [next(m for m in c["messages"] if m["role"] == "user")["content"] for c in corps]


@pytest.mark.asyncio
async def test_l_exploration_tourne_une_boucle_par_sous_question_du_plan(
    db_session, test_user, monkeypatch
):
    _couvertures(monkeypatch, _etat(), _etat())
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Fiche taxe-carbone, plan posé."),
        _texte("Transport : une source."),
        _texte("Industrie : une source."),
        _texte("Positions posées."),
        _texte("Bilan."),
    ]
    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )
    assert _etapes(events).count("exploration") == 2
    consignes = _consignes(corps)
    assert f"Sous-question travaillée : {TRANSPORT}" in consignes[2]
    assert f"Sous-question travaillée : {INDUSTRIE}" in consignes[3]
    assert "rechercher" in {t["function"]["name"] for t in corps[2]["tools"]}
    assert "rechercher" not in {t["function"]["name"] for t in corps[0]["tools"]}


@pytest.mark.asyncio
async def test_le_deroule_relance_une_passe_sur_les_sous_questions_vides(
    db_session, test_user, monkeypatch
):
    # Lectures : avant la passe 1, apres la passe 1, apres la passe 2.
    _couvertures(monkeypatch, _etat(), _etat(TRANSPORT), _etat(TRANSPORT))
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Fiche taxe-carbone, plan posé."),
        _texte("Source ajoutée sur le transport."),
        _texte("Rien trouvé sur l'industrie."),
        _texte("Toujours rien sur l'industrie."),
        _texte("Positions posées."),
        _texte("Bilan."),
    ]
    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )

    assert _etapes(events).count("exploration") == 3
    assert events[-1]["type"] == "done"
    relance = next(c for c in _consignes(corps) if "passe 2" in c)
    assert f"Sous-question travaillée : {INDUSTRIE}" in relance
    assert "Formule autrement" in relance
    assert TRANSPORT not in relance.split("Sous-question travaillée")[1]


@pytest.mark.asyncio
async def test_le_deroule_s_arrete_quand_une_passe_n_ajoute_rien(
    db_session, test_user, monkeypatch
):
    _couvertures(monkeypatch, _etat(), _etat())
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Fiche taxe-carbone, plan posé."),
        _texte("Aucune source ne portait de passage sur le transport."),
        _texte("Aucune source ne portait de passage sur l'industrie."),
        _texte("Aucune position."),
        _texte("Bilan : rien n'a pu être cité."),
    ]
    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )
    assert _etapes(events).count("exploration") == 2
    assert not any("passe 2" in c for c in _consignes(corps))
    assert events[-1]["type"] == "done"


NUANCE = Manque(relecture.SANS_NUANCE, "Taxe carbone", "exploration")
SANS_POSITION = Manque(relecture.SOURCE_SANS_POSITION, "Etude (source_id=s1)", "positions")
VIDE = Manque(relecture.SOUS_QUESTION_VIDE, INDUSTRIE, "exploration")


def _grilles(monkeypatch, *grilles: list[Manque]) -> None:
    """Rend les grilles dans l'ordre des lectures, puis garde la derniere."""
    file = list(grilles)

    async def grille(db, creator_id, slug):
        return file.pop(0) if len(file) > 1 else file[0]

    monkeypatch.setattr(deroule_guide.relecture, "grille", grille)


def _reponses_jusqu_aux_positions() -> list[dict]:
    return [
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Fiche taxe-carbone, plan posé."),
        _texte("Source ajoutée."),
        _texte("Positions posées."),
    ]


@pytest.mark.asyncio
async def test_la_relecture_relance_les_etapes_tant_qu_elle_comble_un_manque(
    db_session, test_user, monkeypatch
):
    # Lectures : avant la relecture, apres le tour 1, apres le tour 2, bilan.
    _grilles(monkeypatch, [NUANCE, SANS_POSITION], [NUANCE], [NUANCE], [NUANCE, VIDE])
    reponses = _reponses_jusqu_aux_positions() + [
        _texte("Relecture 1 : aucune nuance trouvée."),
        _texte("Relecture 1 : position posée."),
        _texte("Relecture 2 : toujours aucune nuance."),
        _texte("Relecture 2 : rien à poser."),
        _texte("Bilan."),
    ]
    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )

    titres = [e["payload"]["titre"] for e in events if e["type"] == "etape_guidee"]
    assert "Relecture 1, exploration" in titres and "Relecture 2, positions" in titres
    assert "Relecture 3, exploration" not in titres
    assert events[-1]["type"] == "done"
    consignes = [next(m for m in c["messages"] if m["role"] == "user")["content"] for c in corps]
    bilan = consignes[-1]
    assert "aucune source qui nuance" in bilan and INDUSTRIE in bilan


@pytest.mark.asyncio
async def test_la_relecture_s_arrete_quand_un_tour_ne_comble_rien(
    db_session, test_user, monkeypatch
):
    _grilles(monkeypatch, [SANS_POSITION], [SANS_POSITION])
    reponses = _reponses_jusqu_aux_positions() + [
        _texte("Relecture 1 : la position n'a pas pu être posée."),
        _texte("Bilan."),
    ]
    events, _ajouts, _heures, _corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )
    titres = [e["payload"]["titre"] for e in events if e["type"] == "etape_guidee"]
    assert titres.count("Relecture 1, positions") == 1
    assert not any(t.startswith("Relecture 2") for t in titres)
    assert "Relecture 1, exploration" not in titres
    assert events[-1]["type"] == "done"
