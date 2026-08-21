"""Mise en forme des schemas d'outils MCP pour les validateurs stricts.

Le validateur de function declarations de Gemini refuse `anyOf`. Or fastmcp le
produit pour tout parametre annote `X | None = None`, ce qui decrit la totalite
de nos parametres optionnels. Resultat cote client : "Provided JSON is invalid
or does not contain any tools", et aucun des 39 outils n'apparait.

Un optionnel se declare tout aussi bien par l'absence du champ dans `required` :
aplatir `anyOf: [T, null]` en `T` ne change donc rien a la semantique, un client
omet simplement le parametre. Les vraies unions (deux variantes non nulles) sont
laissees intactes : les toucher perdrait de l'information.
"""

from __future__ import annotations

from typing import Any


def aplatir_nullable(noeud: Any) -> Any:
    """Remplace recursivement tout `anyOf: [T, {"type": "null"}]` par `T`.

    Rend une structure neuve : ne mute jamais son entree.
    """
    if isinstance(noeud, list):
        return [aplatir_nullable(x) for x in noeud]
    if not isinstance(noeud, dict):
        return noeud

    variantes = noeud.get("anyOf")
    if isinstance(variantes, list):
        non_nulles = [v for v in variantes if not (isinstance(v, dict) and v.get("type") == "null")]
        if len(non_nulles) == 1 and len(non_nulles) < len(variantes):
            # `default: null` disparait avec l'union : le garder decrirait une
            # valeur que le type aplati n'admet plus.
            fusion = {k: v for k, v in noeud.items() if k not in ("anyOf", "default")}
            fusion.update(non_nulles[0])
            return aplatir_nullable(fusion)

    return {k: aplatir_nullable(v) for k, v in noeud.items()}
