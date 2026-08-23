"""Outils Philum de l'agent : les fonctions MCP, mêmes invariants.

Wrappes les fonctions de `app/mcp_server/tools*.py` : elles délèguent déjà
aux services REST, l'agent passe par les mêmes invariants (unicité du slug,
propriété de la ressource, extraits vérifiés). Le `ToolError` MCP devient un
résultat d'erreur que le modèle peut lire et corriger.

**Le LLM propose, la crypto dispose** : toute écriture dans une fiche passe
par les mêmes gardes que le REST et le MCP, et l'agent ne peut jamais toucher
une fiche d'un autre créateur (le `user` du contexte est celui qui appelle).
"""

from __future__ import annotations

import inspect
import types
from typing import Any, cast, get_args, get_origin, get_type_hints

from fastmcp.exceptions import ToolError

from app.agent_tools.tool import AgentTool, ToolContext
from app.mcp_server import tools as lecture
from app.mcp_server import tools_write as ecriture
from app.models.biblio_card import CardKind, CardStatus
from app.models.source import AuthorKind, SourceCategory, SourceFormat, SourceStance
from app.schemas.biblio_card import ContentType, Platform, Visibility

#: Enums par nom de parametre : injectees dans le schema JSON pour que le modele
#: voie les valeurs acceptees et ne parte pas en boucle sur une valeur inventee.
_ENUMS_PAR_PARAMETRE: dict[str, list[str]] = {
    "card_kind": [e.value for e in CardKind],
    "platform": [e.value for e in Platform],
    "content_type": [e.value for e in ContentType],
    "visibility": [e.value for e in Visibility],
    "status": [e.value for e in CardStatus],
    "category": [e.value for e in SourceCategory],
    "author_kind": [e.value for e in AuthorKind],
    "format": [e.value for e in SourceFormat],
    "stance": [e.value for e in SourceStance],
}

#: Paramètres retirés du schéma vu par le modèle.
#:
#: `verify_excerpts(provided_text=...)` fait juger un extrait contre un texte
#: que l'appelant fournit lui-même. Pour un client MCP piloté par une personne,
#: c'est la porte de sortie légitime quand un éditeur bloque la lecture
#: automatique. Pour un agent, c'est une boucle : il écrit l'extrait, puis il
#: écrit le texte qui l'atteste, et la fiche annonce « vérifié » sans que rien
#: d'extérieur ne l'ait confirmé. Sans ce paramètre, la vérification passe
#: toujours par la page que le serveur est allé lire.
_PARAMETRES_MASQUES: dict[str, frozenset[str]] = {
    "verify_excerpts": frozenset({"provided_text"}),
}

#: Actions sensibles : toujours soumises à validation humaine (approbation
#: hybride). Leur exécution ne se fait qu'après un feu vert explicite.
SENSITIVE_TOOLS: frozenset[str] = frozenset(
    {
        "publish_card",
        "delete_card",
        "delete_source",
        "delete_excerpt",
        "create_content_attestation",
        "archive_sources",
    }
)


def est_sensible(name: str, args: dict[str, Any]) -> bool:
    """L'action demandée doit-elle passer par l'approbation humaine ?"""
    if name in SENSITIVE_TOOLS:
        return True
    # `update_card(visibility="public")` publie aussi sûrement que
    # `publish_card` : sans cette branche, l'approbation se contourne en
    # changeant d'outil.
    return name == "update_card" and args.get("visibility") == "public"


def _json_schema(tp: Any) -> dict[str, Any]:
    origin = get_origin(tp)
    args = get_args(tp)
    if origin is list:
        items = _json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": items}
    if origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        return _json_schema(non_none[0]) if non_none else {"type": "string"}
    if tp is str:
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is dict or (origin is dict):
        return {"type": "object"}
    return {"type": "string"}


def _envelopper(fonction, *, avec_utilisateur: bool) -> tuple[dict[str, Any], Any]:
    """Schéma JSON des paramètres + execute qui délègue à la fonction MCP."""
    hints = get_type_hints(fonction)
    masques = _PARAMETRES_MASQUES.get(fonction.__name__, frozenset())
    proprietes: dict[str, Any] = {}
    requis: list[str] = []
    for nom, param in inspect.signature(fonction).parameters.items():
        if nom in ("db", "user") or nom in masques:
            continue
        props = _json_schema(hints.get(nom, str))
        if nom in _ENUMS_PAR_PARAMETRE and props.get("type") == "string":
            props["enum"] = _ENUMS_PAR_PARAMETRE[nom]
        if param.default is inspect.Parameter.empty:
            requis.append(nom)
        else:
            props["default"] = param.default
        proprietes[nom] = props

    async def _execute(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        # Un argument inconnu etait filtre en silence. Le modele qui appelait
        # `add_source(..., excerpt="...")` recevait un succes et annoncait un
        # extrait qui n'existait nulle part. Le dire coute un tour, le taire
        # coute une fausse declaration a l'utilisateur.
        inconnus = sorted(set(args) - set(proprietes))
        if inconnus:
            return {
                "error": (
                    f"{fonction.__name__} n'a pas de parametre "
                    + ", ".join(repr(nom) for nom in inconnus)
                    + ". Parametres acceptes : "
                    + ", ".join(sorted(proprietes))
                    + "."
                )
            }
        manquants = sorted(set(requis) - set(args))
        if manquants:
            return {
                "error": (
                    f"{fonction.__name__} exige "
                    + ", ".join(repr(nom) for nom in manquants)
                    + ", absent{} de l'appel.".format("s" if len(manquants) > 1 else "")
                )
            }
        kwargs = dict(args)
        try:
            resultat = (
                await fonction(ctx.db, ctx.user, **kwargs)
                if avec_utilisateur
                else await fonction(ctx.db, **kwargs)
            )
            return cast("dict[str, Any]", resultat)
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — message lisible par le modèle
            return {"error": f"{fonction.__name__} a échoué : {exc}"}

    return {"type": "object", "properties": proprietes, "required": requis}, _execute


_LECTURE = ("search_cards", "get_card", "get_source", "find_cards_citing")

_ECRITURE = (
    "create_card",
    "add_source",
    "add_excerpt",
    "set_content_text",
    "update_card",
    "update_source",
    "list_my_cards",
    "list_sources",
    "search_my_excerpts",
    "verify_excerpts",
    "publish_card",
    "delete_card",
    "delete_source",
    "delete_excerpt",
    "update_excerpt",
    "suggest_excerpts",
    "annotate_excerpt",
    "parse_biblio",
    "add_sources_batch",
    "get_url_metadata",
    "import_from_content_url",
    "archive_sources",
    "create_content_attestation",
)


def _description(fonction) -> str:
    doc = inspect.cleandoc(fonction.__doc__ or "")
    return " ".join(doc.split()) if doc else fonction.__name__


def philum_tools() -> list[AgentTool]:
    outils: list[AgentTool] = []
    for nom in _LECTURE:
        fn = getattr(lecture, nom)
        schema, execute = _envelopper(fn, avec_utilisateur=False)
        outils.append(
            AgentTool(
                name=nom,
                description=_description(fn),
                parameters=schema,
                output="dict",
                execute=execute,
            )
        )
    for nom in _ECRITURE:
        fn = getattr(ecriture, nom)
        schema, execute = _envelopper(fn, avec_utilisateur=True)
        outils.append(
            AgentTool(
                name=nom,
                description=_description(fn),
                parameters=schema,
                output="dict",
                execute=execute,
            )
        )
    return outils
