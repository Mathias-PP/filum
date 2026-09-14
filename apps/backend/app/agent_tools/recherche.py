"""Outils de recherche de l'agent : `rechercher` une sous-question, lire la `suite_recherche`.

Le modele apporte ce qui demande de comprendre la question, dans toutes les
langues : les formulations de la sous-question et celles qui cherchent ce qui
la contredit. Le serveur execute la methode (`services/recherche_approfondie`) :
collecte large, lecture, passages classes par le sens, suivi des citations et
des liens, arret a saturation. Le modele recoit des passages exacts et numerotes,
et designe par `retenir` ceux qui repondent vraiment : il est le dernier etage
du classement. Le serveur pose alors les sources et les extraits avec le texte
de la page. Mesure du 2026-09-14 : recopier 43 sources passage par passage, un
appel par source, prenait plus que les 20 minutes d'une etape.
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
                "ne nuance le propos dominant. Rien ne bloque : retiens les passages qui "
                "répondent, et dis dans le compte rendu qu'aucune nuance n'a été trouvée."
            )
    if not recherche.sources:
        rendu["message"] = (
            "Aucune page lue ne porte de passage qui réponde. Reformule autrement : autre "
            "vocabulaire, autre discipline, autre langue, ou question redéfinie."
        )
    elif numero < total:
        rendu["suite"] = (
            f"Page {numero} sur {total}. Retiens les passages utiles de cette page avec "
            f'retenir(recherche_id="{recherche.id}", passages), puis '
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
        publications_d_abord=options.publications_d_abord,
    )
    recherche.card_slug = card_slug or None
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
        return {"error": _recherche_perdue(recherche_id)}
    return _page(recherche, numero)


def _recherche_perdue(recherche_id: str) -> str:
    return (
        f"Aucune recherche {recherche_id!r} en mémoire (expirée ou inconnue). "
        "Relance rechercher avec la même sous-question."
    )


def _choix(valeur: Any) -> dict[int, str] | None:
    """Les passages designes, numero vers contexte, dans l'ordre. None si la forme est illisible."""
    if isinstance(valeur, str):
        try:
            valeur = json.loads(valeur)
        except json.JSONDecodeError:
            return None
    if not isinstance(valeur, list):
        return None
    choix: dict[int, str] = {}
    for entree in valeur:
        brut = entree.get("id") if isinstance(entree, dict) else entree
        try:
            numero = int(str(brut).strip())
        except (TypeError, ValueError):
            return None
        contexte = entree.get("contexte") if isinstance(entree, dict) else None
        choix[numero] = " ".join(str(contexte or "").split())
    return choix


async def _execute_retenir(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Pose les passages designes : la source nouvelle avec ses extraits, ou les extraits seuls.

    Le texte vient de la recherche, lu dans la page : le modele ne recopie rien,
    et `add_source` comme `add_excerpt` le retrouvent encore dans la page avant
    d'ecrire, avec toutes leurs gardes.
    """
    from fastmcp.exceptions import ToolError

    from app.extractors.recherche_litterature import Candidate
    from app.mcp_server import tools_write as ecriture
    from app.services.fusion_candidates import identite
    from app.services.recherche_approfondie import retrouver

    recherche_id = str(args.get("recherche_id") or "").strip()
    recherche = retrouver(recherche_id)
    if recherche is None:
        return {"error": _recherche_perdue(recherche_id)}
    card_slug = str(args.get("card_slug") or recherche.card_slug or "").strip()
    if not card_slug:
        return {"error": "retenir attend card_slug : la fiche où poser les passages."}
    choix = _choix(args.get("passages"))
    if not choix:
        return {
            "error": (
                'retenir attend passages : [{"id": id d\'un passage rendu par la recherche, '
                '"contexte": ce que le passage établit}]. Si aucun passage ne répond, '
                "n'appelle pas retenir."
            )
        }
    try:
        sur_la_fiche = await _identites_de_la_fiche(ctx, card_slug)
    except ToolError as exc:
        return {"error": str(exc)}

    par_numero = {p.numero: (s, p) for s in recherche.sources for p in s.passages}
    groupes: dict[int, tuple[Any, list[dict[str, Any]]]] = {}
    for numero, contexte in choix.items():
        if numero in par_numero:
            source, passage = par_numero[numero]
            extrait = {"text": passage.texte, "context": contexte or None}
            groupes.setdefault(id(source), (source, []))[1].append(extrait)

    lignes: list[dict[str, Any]] = []
    ajoutees = poses = 0
    for source, extraits in groupes.values():
        ligne: dict[str, Any] = {"url": source.url_lue, "titre": source.candidate.titre}
        # Une source posee par une recherche precedente de la fiche recoit ses extraits.
        source_id = (
            source.source_id
            or sur_la_fiche.get(identite(source.candidate))
            or sur_la_fiche.get(identite(Candidate(url=source.url_lue, titre=None, famille="")))
        )
        ecrits: list[Any] = []
        refuses: list[str] = []
        try:
            if source_id:
                for extrait in extraits:
                    try:
                        ecrits.append(
                            await ecriture.add_excerpt(
                                ctx.db,
                                ctx.user,
                                source_id=source_id,
                                text=str(extrait["text"]),
                                context=extrait["context"],
                            )
                        )
                    except ToolError as exc:
                        refuses.append(str(exc))
            else:
                resultat = await ecriture.add_source(
                    ctx.db,
                    ctx.user,
                    card_slug=card_slug,
                    url=source.url_lue,
                    doi=source.candidate.doi,
                    metadata_from="page",
                    excerpts=extraits,
                    exiger_extrait=True,
                )
                source_id = str(resultat["id"])
                ajoutees += 1
                ligne["titre"] = resultat.get("title") or ligne["titre"]
                ecrits = list(resultat.get("excerpts") or [])
                refuses = [str(r.get("raison")) for r in resultat.get("excerpts_refuses") or []]
        except ToolError as exc:
            ligne["erreur"] = str(exc)
        except Exception as exc:  # noqa: BLE001  # message lisible par le modèle
            ligne["erreur"] = f"retenir a échoué sur cette source : {exc}"
        if source_id:
            source.source_id = source_id
            ligne["source_id"] = source_id
        poses += len(ecrits)
        ligne["extraits_poses"] = len(ecrits)
        if refuses:
            ligne["extraits_refuses"] = refuses
        lignes.append(ligne)

    rendu: dict[str, Any] = {
        "card_slug": card_slug,
        "sources_ajoutees": ajoutees,
        "extraits_poses": poses,
        "sources": lignes,
    }
    inconnus = [numero for numero in choix if numero not in par_numero]
    if inconnus:
        rendu["ids_inconnus"] = inconnus
    if not poses:
        rendu["error"] = "Aucun extrait posé : voir le détail de chaque source."
    return rendu


def recherche_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="rechercher",
            description=(
                "Cherche les sources d'une sous-question dans le monde entier et rend leurs "
                "passages exacts, classés par pertinence. Le serveur interroge tous les corpus "
                "(web, OpenAlex, Europe PMC, Semantic Scholar), lit les pages, suit les "
                "citations et les liens des sources pertinentes et s'arrête quand plus rien de "
                "nouveau n'arrive. Sauf choix contraire du créateur, les publications "
                "scientifiques et les sites d'institutions sont lus et rendus d'abord, leur "
                "nature dans reference. Chaque passage est une tranche exacte de la page et "
                "porte un id : désigne ceux qui répondent vraiment avec retenir, le serveur les "
                "pose avec le texte de la page."
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
        AgentTool(
            name="retenir",
            description=(
                "Pose sur la fiche les passages choisis parmi ceux que rechercher ou "
                "suite_recherche viennent de rendre, désignés par leur id. Le serveur ajoute les "
                "sources nouvelles et leurs extraits avec le texte exact de la page : rien à "
                "recopier. Un seul appel par page de résultats, avec tous ses passages retenus."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "recherche_id": {
                        "type": "string",
                        "description": "L'identifiant rendu par rechercher.",
                    },
                    "card_slug": {
                        "type": "string",
                        "description": "Slug de la fiche. Par défaut, celle donnée à rechercher.",
                    },
                    "passages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "description": "L'id du passage."},
                                "contexte": {
                                    "type": "string",
                                    "description": (
                                        "Ce que le passage établit pour la question, en une phrase."
                                    ),
                                },
                            },
                            "required": ["id", "contexte"],
                        },
                        "description": (
                            "Les passages qui répondent vraiment à la sous-question ou la nuancent."
                        ),
                    },
                },
                "required": ["recherche_id", "passages"],
            },
            output=(
                "card_slug, sources_ajoutees, extraits_poses, "
                "sources: [{url, titre, source_id, extraits_poses, extraits_refuses, erreur}]"
            ),
            execute=_execute_retenir,
        ),
    ]
