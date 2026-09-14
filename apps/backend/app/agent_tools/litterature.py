"""Outils de decouverte de l'agent : sources multi-corpus et suivi des citations.

`chercher_sources` interroge, pour une requete, les corpus que l'arbitre de
recherche designe (fiches Philum, passages Semantic Scholar, OpenAlex, Europe
PMC, moteurs web) et rend leurs candidates fusionnees par rangs reciproques,
chacune avec sa famille, ses moteurs et ce qu'on en sait deja (DOI, annee,
citations, acces libre).

`references` suit le graphe des citations d'un article pivot : ses fondements
(`references`) ou ce qui l'a confirme, nuance ou contredit depuis (`citants`).

Les deux ne posent rien : ils proposent des adresses reelles, que l'agent
explore ensuite avec `propose_passages`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.agent_tools.tool import AgentTool, ToolContext
from app.core.config import get_settings
from app.extractors.recherche_litterature import (
    Candidate,
    chercher_europepmc,
    chercher_openalex,
    chercher_passages_s2,
    s2_disponible,
    voisinage_openalex,
)
from app.services.profil_modele import PETIT_MODELE, RESULTATS_RECHERCHE_PETIT

#: `chercher_sources` lit les fiches Philum dans la session : jamais en parallele.
OUTILS_LITTERATURE: frozenset[str] = frozenset({"chercher_sources"})

FAMILLES = ("corpus_philum", "passages", "litterature", "biomedical", "web")

#: Candidates rendues au modele. Borne de lisibilite de la reponse d'outil, pas
#: borne editoriale : une autre requete, plus precise, en rend d'autres.
CANDIDATES_RENDUES = 15


async def _fiches_philum(ctx: ToolContext, requete: str) -> list[Candidate]:
    from app.mcp_server import tools as lecture

    base = get_settings().frontend_base_url.rstrip("/")
    fiches = await lecture.search_cards(ctx.db, query=requete, limit=5)
    return [
        Candidate(
            url=f"{base}/@{f['creator']}/{f['slug']}",
            titre=f.get("title"),
            famille="philum",
            sources=["philum"],
            raisons=["fiche Philum : ses extraits sont deja verifies"],
        )
        for f in fiches
        if f.get("creator") and f.get("slug")
    ]


async def _web(requete: str) -> list[Candidate]:
    from app.agent_tools.web import fournisseurs_web, rechercher_web_fusionne

    if not fournisseurs_web():
        return []
    resultats, _repondu = await rechercher_web_fusionne(requete)
    return [
        Candidate(
            url=r["url"],
            titre=r.get("title") or None,
            famille="web",
            sources=(r.get("moteurs") or "web").split(","),
            apercu=(r.get("snippet") or None),
        )
        for r in resultats
        if r.get("url")
    ]


async def _execute_chercher_sources(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools.web import fournisseurs_web
    from app.services.fusion_candidates import fusionner
    from app.services.strategie_recherche import familles_de_recherche, strategie

    requete = str(args.get("requete") or "").strip()
    if not requete:
        return {"error": "chercher_sources attend requete (str)."}
    demandees = args.get("familles")
    if isinstance(demandees, list) and demandees:
        familles = [f for f in (str(x) for x in demandees) if f in FAMILLES]
    else:
        approches = strategie(
            requete,
            [],
            web_disponible=bool(fournisseurs_web()),
            passages_disponibles=s2_disponible(),
        )
        familles = familles_de_recherche(approches)
    if "passages" in familles and not s2_disponible():
        familles.remove("passages")

    listes: list[list[Candidate]] = []
    if "corpus_philum" in familles:
        listes.append(await _fiches_philum(ctx, requete))
    appels = {
        "passages": lambda: chercher_passages_s2(requete),
        "litterature": lambda: chercher_openalex(requete),
        "biomedical": lambda: chercher_europepmc(requete),
        "web": lambda: _web(requete),
    }
    reseau = [f for f in familles if f in appels]
    reponses = await asyncio.gather(*(appels[f]() for f in reseau), return_exceptions=True)
    for reponse in reponses:
        if isinstance(reponse, list):
            listes.append(reponse)

    candidates = fusionner(listes)
    limite = RESULTATS_RECHERCHE_PETIT if PETIT_MODELE.get() else CANDIDATES_RENDUES
    resultat: dict[str, Any] = {
        "requete": requete,
        "familles_interrogees": familles,
        "candidates": [c.en_dict() for c in candidates[:limite]],
    }
    if not candidates:
        resultat["message"] = (
            "Aucune source trouvée. Reformule la requête (autres mots, autre langue, "
            "question plus précise) ou interroge une autre famille."
        )
    else:
        resultat["suite"] = (
            "Pour chaque candidate utile : propose_passages(url, questions). Pour un article "
            "pivot (très cité, synthèse, méta-analyse) : references(doi, sens='citants') "
            "trouve ce qui le confirme ou le contredit."
        )
    return resultat


async def _execute_references(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doi = str(args.get("doi") or "").strip()
    sens = str(args.get("sens") or "citants").strip()
    if not doi:
        return {"error": "references attend doi (str)."}
    if sens not in ("citants", "references"):
        return {
            "error": "sens vaut 'citants' (ce qui cite l'article) ou 'references' (ce qu'il cite)."
        }
    limite = RESULTATS_RECHERCHE_PETIT if PETIT_MODELE.get() else CANDIDATES_RENDUES
    candidates = await voisinage_openalex(doi, sens=sens, limite=limite)
    resultat: dict[str, Any] = {
        "doi": doi,
        "sens": sens,
        "candidates": [c.en_dict() for c in candidates],
    }
    if not candidates:
        resultat["message"] = (
            "OpenAlex ne connaît pas ce DOI ou ne lui associe aucun article dans ce sens."
        )
    return resultat


def litterature_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="chercher_sources",
            description=(
                "Cherche des sources pour une requête dans plusieurs corpus à la fois (fiches "
                "Philum, littérature scientifique OpenAlex, biomédical Europe PMC, passages "
                "Semantic Scholar, moteurs web) et rend des candidates réelles, fusionnées et "
                "classées, avec leur famille, DOI, année, citations et accès libre. Sans "
                "`familles`, l'arbitre choisit les corpus selon la requête."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "requete": {
                        "type": "string",
                        "description": "Une question précise, ou un aspect de la question.",
                    },
                    "familles": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(FAMILLES)},
                        "description": "Corpus à interroger, dans l'ordre. Facultatif.",
                    },
                },
                "required": ["requete"],
            },
            output="dict",
            execute=_execute_chercher_sources,
        ),
        AgentTool(
            name="references",
            description=(
                "Suit les citations d'un article pivot par son DOI : sens='citants' rend les "
                "articles qui le citent, du plus récent au plus ancien (confirmations, nuances, "
                "contradictions) ; sens='references' rend ce qu'il cite, du plus cité au moins "
                "cité (fondements)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "doi": {"type": "string", "description": "DOI de l'article pivot."},
                    "sens": {"type": "string", "enum": ["citants", "references"]},
                },
                "required": ["doi"],
            },
            output="dict",
            execute=_execute_references,
        ),
    ]
