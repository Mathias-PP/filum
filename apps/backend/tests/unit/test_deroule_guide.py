"""Le deroule guide d'une fiche sujet, tenu par le serveur.

Mesure du 2026-09-13 : laisse libre, l'agent repondait de memoire et
n'appelait jamais les outils de deroule.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from app.agent_tools.deroule import deroule_tools
from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.crypto.keygen import KeyManager
from app.models.agent_provider import AgentProvider
from app.services import citations_bilan, deroule_guide, relecture
from app.services.couverture import Couverture, SousQuestion
from app.services.deroule_guide import ETAPES, est_demande_de_fiche, relancer_une_passe
from app.services.options_recherche import Options
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


async def _derouler(
    db_session, test_user, reponses: list[dict], slug="prevention-arthrose", **options
):
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
        **{outil.name: outil for outil in deroule_tools()},
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
        **options,
    )
    return events, ajouts, heures, corps


def _etapes(events: list[dict]) -> list[str]:
    return [e["payload"]["etape"] for e in events if e["type"] == "etape_guidee"]


@pytest.mark.asyncio
async def test_les_etapes_se_deroulent_dans_l_ordre(db_session, test_user):
    reponses = [
        _texte("La question est claire."),
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
        in next(m for m in corps[3]["messages"] if m["role"] == "user")["content"]
    )
    # Sans reponse attendue, aucune question n'est posee.
    assert not any(e["type"] == "question_guidee" for e in events)
    assert [e["type"] for e in events].count("done") == 1
    assert events[-1]["type"] == "done"
    # Chaque etape ne voit que ses outils.
    noms_etape_1 = {t["function"]["name"] for t in corps[0]["tools"]}
    assert noms_etape_1 <= set(ETAPES[0].outils)
    assert "add_excerpt" not in noms_etape_1
    # La fiche creee est donnee aux etapes suivantes.
    consigne_etape_2 = next(m for m in corps[3]["messages"] if m["role"] == "user")["content"]
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
        db_session, test_user, [_texte("Claire."), _texte("Je n'ai rien trouvé.")]
    )
    assert _etapes(events) == ["cadrage", "plan"]
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
        _texte("Claire."),
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
    assert f"Sous-question travaillée : {TRANSPORT}" in consignes[3]
    assert f"Sous-question travaillée : {INDUSTRIE}" in consignes[4]
    assert "rechercher" in {t["function"]["name"] for t in corps[3]["tools"]}
    assert "rechercher" not in {t["function"]["name"] for t in corps[1]["tools"]}


@pytest.mark.asyncio
async def test_le_deroule_relance_une_passe_sur_les_sous_questions_vides(
    db_session, test_user, monkeypatch
):
    # Lectures : avant la passe 1, apres la passe 1, apres la passe 2.
    _couvertures(monkeypatch, _etat(), _etat(TRANSPORT), _etat(TRANSPORT))
    reponses = [
        _texte("Claire."),
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
        _texte("Claire."),
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
        _texte("Claire."),
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


@pytest.mark.asyncio
async def test_une_precision_part_au_createur_et_guide_la_suite(db_session, test_user):
    reponses = [
        _appel("demander_precision", {"question": "Pour qui ?", "options": ["Adultes", "Enfants"]}),
        _texte("Précision demandée."),
        _texte("Je n'ai rien trouvé."),
    ]
    posees: list[str] = []

    async def attendre(request_id):
        posees.append(request_id)
        return {"choix": "Adultes"}

    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, attendre=attendre
    )
    question = next(e for e in events if e["type"] == "question_guidee")["payload"]
    assert question["genre"] == "precision"
    assert question["options"] == ["Adultes", "Enfants"]
    assert posees == [question["request_id"]]
    assert any(e["type"] == "question_resolue" for e in events)
    assert "Précision du créateur\nAdultes" in _consignes(corps)[2]


@pytest.mark.asyncio
async def test_le_plan_est_montre_au_createur_qui_le_corrige(db_session, test_user, monkeypatch):
    _couvertures(monkeypatch, _etat(), _etat())
    ecrits: list[list[str]] = []

    async def lire_plan(db, creator_id, slug):
        return [TRANSPORT, INDUSTRIE]

    async def ecrire_plan(db, creator_id, slug, sous_questions):
        ecrits.append(sous_questions)
        return sous_questions

    monkeypatch.setattr(deroule_guide.couverture, "lire_plan", lire_plan)
    monkeypatch.setattr(deroule_guide.couverture, "ecrire_plan", ecrire_plan)

    async def attendre(request_id):
        return {"sous_questions": [INDUSTRIE]}

    reponses = [
        _texte("Claire."),
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Plan posé."),
        _texte("Transport."),
        _texte("Industrie."),
        _texte("Positions."),
        _texte("Bilan."),
    ]
    events, _ajouts, _heures, corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone", attendre=attendre
    )
    question = next(e for e in events if e["type"] == "question_guidee")["payload"]
    assert question["genre"] == "plan" and question["sous_questions"] == [TRANSPORT, INDUSTRIE]
    assert ecrits == [[INDUSTRIE]]
    assert "Plan corrigé par le créateur" in _consignes(corps)[3]


@pytest.mark.asyncio
async def test_le_mode_rapide_garde_la_methode_et_retire_les_budgets(
    db_session, test_user, monkeypatch
):
    # En mode approfondi, cette couverture relancerait une passe sur l'industrie.
    _couvertures(monkeypatch, _etat(), _etat(TRANSPORT))
    _grilles(monkeypatch, [SANS_POSITION])
    reponses = [
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Plan posé."),
        _texte("Transport."),
        _texte("Industrie."),
        _texte("Positions."),
        _texte("Bilan."),
    ]

    async def attendre(request_id):
        raise AssertionError("le mode rapide ne pose aucune question")

    events, _ajouts, _heures, _corps = await _derouler(
        db_session,
        test_user,
        reponses,
        slug="taxe-carbone",
        options=Options(mode="rapide"),
        attendre=attendre,
    )
    titres = [e["payload"]["titre"] for e in events if e["type"] == "etape_guidee"]
    assert "cadrage" not in _etapes(events)
    assert _etapes(events).count("exploration") == 2
    assert not any(t.startswith("Relecture") for t in titres)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_une_suite_explore_seulement_sa_sous_question(db_session, test_user, monkeypatch):
    _couvertures(monkeypatch, _etat(TRANSPORT))
    ecrits: list[list[str]] = []

    async def lire_plan(db, creator_id, slug):
        return [TRANSPORT]

    async def ecrire_plan(db, creator_id, slug, sous_questions):
        ecrits.append(sous_questions)
        return sous_questions

    monkeypatch.setattr(deroule_guide.couverture, "lire_plan", lire_plan)
    monkeypatch.setattr(deroule_guide.couverture, "ecrire_plan", ecrire_plan)
    reponses = [_texte("Industrie : une source."), _texte("Positions."), _texte("Bilan.")]

    events, _ajouts, _heures, corps = await _derouler(
        db_session,
        test_user,
        reponses,
        slug="taxe-carbone",
        suite=deroule_guide.Suite("taxe-carbone", INDUSTRIE),
    )
    assert _etapes(events) == ["exploration", "positions", "bilan"]
    assert ecrits == [[TRANSPORT, INDUSTRIE]]
    assert f"Sous-question travaillée : {INDUSTRIE}" in _consignes(corps)[0]


@pytest.mark.asyncio
async def test_le_bilan_lie_ses_renvois_et_propose_des_suites(db_session, test_user, monkeypatch):
    _couvertures(monkeypatch, _etat(), _etat())
    identifiant = "11111111-1111-4111-8111-111111111111"

    async def lier(db, creator_id, username, slug, texte):
        assert f"[extrait:{identifiant}]" in texte
        return citations_bilan.ReponseLiee("La taxe marche. [1](https://philum.test/x)", 1, 0)

    monkeypatch.setattr(deroule_guide.citations_bilan, "lier", lier)
    reponses = [
        _texte("Claire."),
        _appel("create_card", {"card_kind": "sujet", "slug": "taxe-carbone"}),
        _texte("Plan posé."),
        _texte("Transport."),
        _texte("Industrie."),
        _texte("Positions."),
        _appel("proposer_suites", {"questions": ["Et chez les enfants ?"]}),
        _texte(f"La taxe marche. [extrait:{identifiant}]"),
    ]
    events, _ajouts, _heures, _corps = await _derouler(
        db_session, test_user, reponses, slug="taxe-carbone"
    )
    verifiee = next(e for e in events if e["type"] == "reponse_verifiee")["payload"]
    assert verifiee["texte"] == "La taxe marche. [1](https://philum.test/x)"
    suites = next(e for e in events if e["type"] == "suites_proposees")["payload"]
    assert suites == {"card_slug": "taxe-carbone", "questions": ["Et chez les enfants ?"]}
    assert events[-1]["type"] == "done"
