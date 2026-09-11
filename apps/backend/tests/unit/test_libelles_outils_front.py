"""Chaque outil que l'agent peut appeler a un libelle lisible dans l'interface.

Sans entree dans `toolLabels.ts`, la carte d'outil affichait le nom technique
tel quel (`get_my_card`) : le createur lisait un identifiant de code la ou il
attendait une action. La table est ecrite a la main, cote front, et elle avait
deja diverge du registre cinq fois. Ce test lit les deux et echoue au premier
outil ajoute sans libelle : la garantie ne depend pas de la memoire de celui
qui ajoute l'outil.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.agent_tools.registry import noms_outils_connus

LIBELLES = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "agent" / "toolLabels.ts"
)


def _noms_libelles() -> set[str]:
    source = LIBELLES.read_text(encoding="utf-8")
    debut = source.index("const ACTIONS")
    fin = source.index("\n};", debut)
    return set(re.findall(r"^\s{2}([a-z_]+):\s*\{", source[debut:fin], flags=re.MULTILINE))


def test_la_table_des_libelles_est_lisible():
    # Garde contre un test qui passerait a vide si la forme du fichier changeait.
    assert len(_noms_libelles()) > 20


def test_chaque_outil_du_registre_a_un_libelle():
    manquants = sorted(noms_outils_connus() - _noms_libelles())
    assert not manquants, f"Outils sans libelle dans toolLabels.ts : {manquants}"
