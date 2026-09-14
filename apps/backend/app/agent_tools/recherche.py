"""Outils de recherche de l'agent : `rechercher` une sous-question, lire la `suite_recherche`.

Le modele apporte ce qui demande de comprendre la question, dans toutes les
langues : les formulations de la sous-question et celles qui cherchent ce qui
la contredit. Le serveur execute la methode (`services/recherche_approfondie`) :
collecte large, lecture, passages classes par le sens, suivi des citations et
des liens, arret a saturation. Le modele recoit des passages exacts, choisit
ceux qui repondent vraiment et les pose : il est le dernier etage du classement.
"""

from __future__ import annotations

import json
from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext
from app.services.profil_modele import FENETRE_LECTURE_PETIT, PETIT_MODELE
from app.services.recherche_approfondie import NUANCE

#: `rechercher` lit les sources de la fiche dans la session : jamais en parallele.
OUTILS_RECHERCHE: frozenset[str] = frozenset({"rechercher"})

#: Budget d'une page de resultats, en caracteres, pour un grand modele. Un tiers
#: du plafond d'un resultat d'outil (`TOOL_RESULT_MAX`) : la page doit laisser la
#: place aux poses qui la suivent dans la meme boucle. Un petit modele recoit la
#: fenetre mesuree pour la lecture d'une page (`FENETRE_LECTURE_PETIT`).
PAGE_RESULTATS = 40_000


def _liste(valeur: Any) -> list[str] | None:
    if isinstance(valeur, str):
        try:
            valeur = json.loads(valeur)
        except json.JSONDecodeError:
            valeur = [valeur]
    if not isinstance(valeur, list):
        return None
    return [str(v).strip() for v in valeur if str(v).strip()]


def _budget() -> int:
    return FENETRE_LECTURE_PETIT if PETIT_MODELE.get() else PAGE_RESULTATS


def _page(recherche: Any, numero: int) -> dict[str, Any]:
    from app.services.recherche_approfondie import pages

    decoupe = pages(recherche.sources, _budget())
    total = len(decoupe)
    rendu: dict[str, Any] = {
        "recherche_id": recherche.id,
        "sous_question": recherche.sous_question,
        "page": numero,
        "pages": total,
        "sources_pertinentes": len(recherche.sources),
        "sources": [s.en_dict() for s in decoupe[numero - 1]] if 0 < numero <= total else [],
    }
    nuances = sum(1 for s in recherche.sources for p in s.passages if p.role == NUANCE)
    if numero == 1:
        rendu["journal"] = recherche.journal.en_dict()
        rendu["passages_qui_nuancent"] = nuances
        if recherche.sources and not nuances:
            # Chercher ce qui contredit est exige ; le trouver ne peut pas l'etre.
            # Une recherche honnete qui ne trouve aucune nuance ne bloque rien.
            rendu["nuance"] = (
                "La recherche de contradiction a eu lieu et aucun passage lu ne contredit ni "
                "ne nuance le propos dominant. Rien ne bloque : pose les passages qui "
                "répondent, et dis dans le compte rendu qu'aucune nuance n'a été trouvée."
            )
    if not recherche.sources:
        rendu["message"] = (
            "Aucune page lue ne porte de passage qui réponde. Reformule autrement : autre "
            "vocabulaire, autre discipline, autre langue, ou question redéfinie."
        )
    elif numero < total:
        rendu["suite"] = (
            f"Page {numero} sur {total}. Pose les passages utiles de cette page, puis "
            f'suite_recherche(recherche_id="{recherche.id}", page={numero + 1}).'
        )
    return rendu


async def _identites_de_la_fiche(ctx: ToolContext, card_slug: str) -> dict[str, str]:
    from sqlalchemy import select

    from app.extractors.recherche_litterature import Candidate
    from app.mcp_server.tools_write import _fiche_du_createur
    from app.models.source import Source
    from app.services.fusion_candidates import identite

    card = await _fiche_du_createur(ctx.db, ctx.user, card_slug)
    lignes = await ctx.db.execute(
        select(Source.id, Source.url, Source.doi).where(
            Source.biblio_card_id == card.id, Source.deleted_at.is_(None)
        )
    )
    return {
        identite(Candidate(url=url, titre=None, famille="", doi=doi)): str(source_id)
        for source_id, url, doi in lignes.all()
    }


async def _execute_rechercher(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from fastmcp.exceptions import ToolError

    from app.services.options_recherche import filtrer_corpus, options_courantes
    from app.services.recherche_approfondie import (
        corpus_configures,
        garder,
        rechercher_sous_question,
    )

    sous_question = str(args.get("sous_question") or "").strip()
    requetes = _liste(args.get("requetes"))
    contradictions = _liste(args.get("requetes_contradiction"))
    if not sous_question:
        return {
            "error": "rechercher attend sous_question : la question que les sources doivent éclairer."
        }
    if not requetes:
        return {
            "error": (
                "rechercher attend requetes : au moins une formulation de la sous-question, "
                "et de préférence plusieurs qui diffèrent vraiment (vocabulaire technique, "
                "synonymes, langues où le sujet est étudié)."
            )
        }
    if not contradictions:
        return {
            "error": (
                "rechercher attend requetes_contradiction : au moins une formulation qui "
                "cherche ce qui contredit ou nuance le propos dominant (limites, critiques, "
                "résultats contraires). Une recherche qui ne le cherche pas n'est pas finie. "
                "Si elle ne trouve rien, rien ne bloque."
            )
        }
    deja: dict[str, str] = {}
    card_slug = str(args.get("card_slug") or "").strip()
    if card_slug:
        try:
            deja = await _identites_de_la_fiche(ctx, card_slug)
        except ToolError as exc:
            return {"error": str(exc)}
    options = options_courantes()
    recherche = await rechercher_sous_question(
        sous_question,
        requetes,
        contradictions,
        deja=deja,
        corpus=filtrer_corpus(corpus_configures(), options),
        # Mode rapide : même méthode, sans les tours de suivi des citations.
        expansion=not options.rapide,
        serieuses_d_abord=options.serieuses_d_abord,
    )
    garder(recherche)
    return _page(recherche, 1)


async def _execute_suite_recherche(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.recherche_approfondie import retrouver

    recherche_id = str(args.get("recherche_id") or "").strip()
    try:
        numero = int(args.get("page") or 2)
    except (TypeError, ValueError):
        return {"error": "page attend un nombre entier."}
    recherche = retrouver(recherche_id)
    if recherche is None:
        return {
            "error": (
                f"Aucune recherche {recherche_id!r} en mémoire (expirée ou inconnue). "
                "Relance rechercher avec la même sous-question."
            )
        }
    return _page(recherche, numero)


def recherche_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="rechercher",
            description=(
                "Cherche les sources d'une sous-question dans le monde entier et rend leurs "
                "passages exacts, classés par pertinence. Le serveur interroge tous les corpus "
                "(web, OpenAlex, Europe PMC, Semantic Scholar), lit les pages, suit les "
                "citations et les liens des sources pertinentes et s'arrête quand plus rien de "
                "nouveau n'arrive. Sauf choix contraire du créateur, les références sérieuses "
                "(articles, institutions publiques, universités) sont lues et rendues d'abord, "
                "leur nature dans reference. Chaque passage rendu est une tranche exacte de la page : "
                "recopie tels quels ceux qui répondent vraiment dans add_source(url, "
                "excerpts=[...]), ou add_excerpt(source_id, text) quand la source est déjà sur "
                "la fiche."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "card_slug": {
                        "type": "string",
                        "description": "Slug de la fiche : ses sources déjà posées sont reconnues.",
                    },
                    "sous_question": {
                        "type": "string",
                        "description": "La question précise que les sources doivent éclairer.",
                    },
                    "requetes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Formulations de la sous-question qui diffèrent vraiment : "
                            "vocabulaire technique du domaine, synonymes, noms de mesures, "
                            "d'études ou d'institutions, et les langues où le sujet est étudié."
                        ),
                    },
                    "requetes_contradiction": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Formulations qui cherchent ce qui contredit ou nuance le propos "
                            "dominant : limites, critiques, résultats contraires. Au moins une ; "
                            "ne rien trouver ne bloque pas."
                        ),
                    },
                },
                "required": ["sous_question", "requetes", "requetes_contradiction"],
            },
            output="recherche_id, page, pages, sources: [{url, titre, doi, passages}], journal",
            execute=_execute_rechercher,
        ),
        AgentTool(
            name="suite_recherche",
            description="Rend la page suivante des sources d'une recherche déjà faite.",
            parameters={
                "type": "object",
                "properties": {
                    "recherche_id": {"type": "string"},
                    "page": {"type": "integer", "description": "Numéro de la page (2 et plus)."},
                },
                "required": ["recherche_id", "page"],
            },
            output="recherche_id, page, pages, sources",
            execute=_execute_suite_recherche,
        ),
    ]
