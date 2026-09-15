"""L'historique envoye au modele : appels et reponses apparies, identifiants au format du fournisseur.

Mesure du 2026-09-15 (conversation « harness ») : des messages enregistres a la
meme heure se relisaient dans le desordre, et Mistral refusait chaque message
suivant de la conversation en 400.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.api.v1.endpoints.agent_chat import heures_croissantes
from app.services.agent import _id_mistral, _nettoyer_messages


def _appel(ident: str, nom: str = "get_source") -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": ident, "type": "function", "function": {"name": nom, "arguments": "{}"}}
        ],
    }


def _reponse(ident: str, contenu: str = '{"ok": true}') -> dict:
    return {"role": "tool", "tool_call_id": ident, "name": "get_source", "content": contenu}


def test_les_reponses_sont_replacees_derriere_leur_appel_et_un_appel_perdu_le_dit():
    historique = [
        {"role": "user", "content": "Relis la fiche"},
        _appel("call_a"),
        _appel("call_b"),
        _reponse("call_b"),
        _reponse("call_a"),
        _reponse("call_inconnu"),
        _appel("call_c"),
        {"role": "assistant", "content": "Voici."},
    ]

    envoye = _nettoyer_messages(historique, None, "openai")

    roles = [(m["role"], m.get("tool_call_id") or "") for m in envoye]
    assert roles == [
        ("user", ""),
        ("assistant", ""),
        ("tool", "call_a"),
        ("assistant", ""),
        ("tool", "call_b"),
        ("assistant", ""),
        ("tool", "call_c"),
        ("assistant", ""),
    ]
    assert "pas été conservé" in envoye[6]["content"]
    assert all(m.get("tool_call_id") != "call_inconnu" for m in envoye)


def test_vers_mistral_les_identifiants_ont_neuf_caracteres_et_restent_apparies():
    envoye = _nettoyer_messages(
        [_appel("call_d060db63aeec42a6867db4a5"), _reponse("call_d060db63aeec42a6867db4a5")],
        None,
        "mistral",
    )
    ident = envoye[0]["tool_calls"][0]["id"]
    assert re.fullmatch(r"[A-Za-z0-9]{9}", ident)
    assert envoye[1]["tool_call_id"] == ident
    assert _id_mistral("aB3dE5gH9") == "aB3dE5gH9"
    assert _id_mistral("call_x") == _id_mistral("call_x") != _id_mistral("call_y")


def test_les_autres_fournisseurs_gardent_leurs_identifiants():
    envoye = _nettoyer_messages([_appel("call_zai_1"), _reponse("call_zai_1")], None, "gemini")
    assert envoye[0]["tool_calls"][0]["id"] == "call_zai_1"


def test_les_messages_d_un_tour_ont_des_heures_strictement_croissantes():
    midi = datetime(2026, 9, 14, 18, 9, 15)
    heures = heures_croissantes([midi, midi, midi - timedelta(seconds=1)], 4)
    assert len(heures) == 4
    assert all(a < b for a, b in zip(heures, heures[1:], strict=False))
    assert heures[0] == midi
