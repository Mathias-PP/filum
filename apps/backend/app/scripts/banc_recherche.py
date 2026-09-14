"""Banc de la recherche : retrouve-t-on les sources qu'une revue de la litterature a retenues ?

Point 9 du plan de la methode de recherche (etude du 2026-09-14). La reference
d'une question est la liste des travaux cites par une revue publiee : des
specialistes du domaine les ont retenus, dans n'importe quelle discipline et
n'importe quelle langue. C'est la methode des evaluations de rappel sur revues
(LitSearch, ScholarQA-CS), appliquee a tous les domaines d'OpenAlex.

Trois commandes :

- `construire` tire des revues dans OpenAlex, domaine par domaine, avec leurs
  references ;
- `jouer` lance la recherche de Philum sur chaque question et mesure le rappel,
  avec des ablations (`--sans <corpus>`, `--sans-suivi`, `--lot`) : c'est ce qui
  dit ce que chaque approche apporte ;
- `noter` note avec les memes mesures les adresses rendues par un autre outil
  (Perplexity, Gemini, OpenAI) sur les memes questions.

La revue elle-meme est exclue des candidates : suivre ses references donnerait
la reponse. La recherche lit des pages, calcule des embeddings et interroge les
corpus configures : a lancer la ou ils le sont, sans jamais passer de secret en
argument. Chaque formulation coute un credit au moteur web ; `--sans web` pour
un grand jeu.

    uv run python -m app.scripts.banc_recherche construire --par-domaine 3
    uv run python -m app.scripts.banc_recherche jouer banc-recherche/jeu.json --sans web
    uv run python -m app.scripts.banc_recherche noter banc-recherche/jeu.json --externe autre.json

`--formulations fichier.json` (`{id: {requetes, requetes_contradiction}}`) joue
des formulations ecrites par un modele ; sans lui, la question est la seule
formulation, ce qui mesure la methode du serveur seule.

Ne rien importer de l'application en tete de module : les tests importent les
fonctions pures sans configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Les quatre domaines d'OpenAlex (`/domains`, releve le 2026-09-14).
DOMAINES: dict[int, str] = {
    1: "Life Sciences",
    2: "Social Sciences",
    3: "Physical Sciences",
    4: "Health Sciences",
}

#: References minimales d'une revue retenue. Bruit de mesure : sur une revue a
#: trois references, le rappel ne peut valoir que 0, 33, 67 ou 100 %. Reglable.
REFERENCES_MIN = 20

_IDENTIFIANTS_PAR_FILTRE = 100


def _doi(valeur: str | None) -> str | None:
    propre = (valeur or "").strip().lower()
    propre = propre.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return propre or None


def question_depuis_revue(travail: dict[str, Any]) -> dict[str, Any] | None:
    """Une revue OpenAlex en question du banc, sans ses references. Fonction pure."""
    titre = " ".join(str(travail.get("display_name") or "").split())
    doi = _doi(travail.get("doi"))
    if not titre or not doi:
        return None
    return {
        "id": str(travail.get("id") or "").rsplit("/", 1)[-1],
        "question": titre,
        "doi": doi,
        "annee": travail.get("publication_year"),
        "langue": travail.get("language"),
    }


def mesures(reference: list[str], trouvees: list[str], vues: set[str]) -> dict[str, Any]:
    """Le rappel d'une recherche contre la reference d'une question. Fonction pure.

    - `rappel` : part de la reference parmi les sources pertinentes rendues ;
    - `rappel_aux_r_premieres` : la meme part parmi les R premieres, R etant la
      taille de la reference (R-precision) : l'ordre compte ;
    - `rappel_de_la_collecte` : part de la reference parmi toutes les candidates
      vues, lues ou non : ce que la lecture et le classement ont perdu se lit
      dans l'ecart avec `rappel`.
    """
    attendus = {d for d in (_doi(r) for r in reference) if d}
    rendues = [d for d in (_doi(t) for t in trouvees) if d]
    if not attendus:
        return {"reference": 0, "rappel": None, "rappel_aux_r_premieres": None}
    trouves = attendus & set(rendues)
    return {
        "reference": len(attendus),
        "rappel": round(len(trouves) / len(attendus), 3),
        "rappel_aux_r_premieres": round(
            len(attendus & set(rendues[: len(attendus)])) / len(attendus), 3
        ),
        "rappel_de_la_collecte": round(len(attendus & {_doi(v) for v in vues}) / len(attendus), 3),
        "trouvees_hors_reference": len(set(rendues) - attendus),
    }


async def _dois_des_references(identifiants: list[str]) -> list[str]:
    from app.extractors.openalex_client import entetes_openalex
    from app.extractors.recherche_litterature import PAGE_OPENALEX, _get_json

    courts = [str(i).rsplit("/", 1)[-1] for i in identifiants]
    dois: list[str] = []
    for debut in range(0, len(courts), _IDENTIFIANTS_PAR_FILTRE):
        charge = await _get_json(
            "https://api.openalex.org/works",
            params={
                "filter": "openalex_id:"
                + "|".join(courts[debut : debut + _IDENTIFIANTS_PAR_FILTRE]),
                "select": "id,doi",
                "per_page": PAGE_OPENALEX,
            },
            entetes=entetes_openalex(),
        )
        dois += [d for w in (charge or {}).get("results") or [] if (d := _doi(w.get("doi")))]
    return dois


async def construire(
    par_domaine: int, depuis: str, graine: int, references_min: int
) -> list[dict[str, Any]]:
    from app.extractors.openalex_client import entetes_openalex
    from app.extractors.recherche_litterature import _get_json

    jeu: list[dict[str, Any]] = []
    for domaine, nom in DOMAINES.items():
        charge = await _get_json(
            "https://api.openalex.org/works",
            params={
                "filter": (
                    f"type:review,primary_topic.domain.id:{domaine},"
                    f"referenced_works_count:>{references_min},has_doi:true,"
                    f"from_publication_date:{depuis}"
                ),
                "sample": par_domaine,
                "seed": graine,
                "per_page": par_domaine,
                "select": "id,doi,display_name,publication_year,language,referenced_works",
            },
            entetes=entetes_openalex(),
        )
        for travail in (charge or {}).get("results") or []:
            question = question_depuis_revue(travail)
            if question is None:
                continue
            question["domaine"] = nom
            question["reference"] = await _dois_des_references(
                travail.get("referenced_works") or []
            )
            jeu.append(question)
            print(
                f"... {nom} : {question['question'][:70]} ({len(question['reference'])} DOI)",
                flush=True,
            )
    return jeu


async def jouer_question(
    entree: dict[str, Any],
    *,
    sans: set[str],
    suivi: bool,
    lot: int,
    formulations: dict[str, Any],
) -> dict[str, Any]:
    from app.services.content_identity import extract_doi
    from app.services.recherche_approfondie import corpus_configures, rechercher_sous_question

    corpus = {nom: f for nom, f in corpus_configures().items() if nom not in sans}
    propres = formulations.get(entree["id"]) or {}
    recherche = await rechercher_sous_question(
        entree["question"],
        propres.get("requetes") or [entree["question"]],
        propres.get("requetes_contradiction") or [],
        corpus=corpus,
        exclure=frozenset({f"doi:{entree['doi']}"}),
        expansion=suivi,
        lot=lot,
    )
    trouvees = [
        d for s in recherche.sources if (d := _doi(s.candidate.doi or extract_doi(s.url_lue)))
    ]
    vues = {v.removeprefix("doi:") for v in recherche.vues if v.startswith("doi:")}
    return {
        "id": entree["id"],
        "domaine": entree.get("domaine"),
        "question": entree["question"],
        "corpus": sorted(corpus),
        "sources_pertinentes": len(recherche.sources),
        **mesures(entree["reference"], trouvees, vues),
        "journal": recherche.journal.en_dict(),
    }


async def noter_externe(entree: dict[str, Any], adresses: list[str]) -> dict[str, Any]:
    from app.extractors.url_extractor import resolve_doi_from_url
    from app.services.content_identity import extract_doi

    async def doi_de(adresse: str) -> str | None:
        if adresse.strip().lower().startswith("10."):
            return _doi(adresse)
        return _doi(extract_doi(adresse) or await resolve_doi_from_url(adresse))

    dois = await asyncio.gather(*(doi_de(a) for a in adresses))
    trouvees = [d for d in dois if d]
    return {
        "id": entree["id"],
        "domaine": entree.get("domaine"),
        "question": entree["question"],
        "adresses": len(adresses),
        "adresses_sans_doi": len(adresses) - len(trouvees),
        **mesures(entree["reference"], trouvees, set(trouvees)),
    }


def tableau(resultats: list[dict[str, Any]]) -> str:
    colonnes = (
        ("domaine", "Domaine"),
        ("question", "Question"),
        ("reference", "Référence"),
        ("rappel", "Rappel"),
        ("rappel_aux_r_premieres", "Rappel aux R premières"),
        ("rappel_de_la_collecte", "Rappel de la collecte"),
        ("sources_pertinentes", "Sources pertinentes"),
    )
    lignes = ["| " + " | ".join(t for _, t in colonnes) + " |", "|" + "---|" * len(colonnes)]
    for r in resultats:
        valeurs = [str(r.get(cle) if r.get(cle) is not None else "") for cle, _ in colonnes]
        valeurs[1] = valeurs[1][:50]
        lignes.append("| " + " | ".join(valeurs) + " |")
    return "\n".join(lignes)


def _ecrire(sortie: Path, nom: str, resultats: list[dict[str, Any]]) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    fichier = sortie / f"{nom}-{horodatage}.json"
    fichier.write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(tableau(resultats))
    print(f"\nRésultats complets : {fichier}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commandes = parser.add_subparsers(dest="commande", required=True)

    c = commandes.add_parser("construire")
    c.add_argument("--par-domaine", type=int, default=3)
    c.add_argument("--depuis", default="2023-01-01")
    c.add_argument("--graine", type=int, default=2026)
    c.add_argument("--references-min", type=int, default=REFERENCES_MIN)
    c.add_argument("--sortie", type=Path, default=Path("banc-recherche/jeu.json"))

    j = commandes.add_parser("jouer")
    j.add_argument("jeu", type=Path)
    j.add_argument("--sans", action="append", default=[], help="corpus a retirer (ablation)")
    j.add_argument("--sans-suivi", action="store_true")
    j.add_argument("--lot", type=int, default=None)
    j.add_argument("--formulations", type=Path, default=None)
    j.add_argument("--sortie", type=Path, default=Path("banc-recherche"))

    n = commandes.add_parser("noter")
    n.add_argument("jeu", type=Path)
    n.add_argument("--externe", type=Path, required=True, help="{id: [adresses ou DOI]}")
    n.add_argument("--sortie", type=Path, default=Path("banc-recherche"))

    arguments = parser.parse_args()
    if arguments.commande == "construire":
        jeu = asyncio.run(
            construire(
                arguments.par_domaine, arguments.depuis, arguments.graine, arguments.references_min
            )
        )
        arguments.sortie.parent.mkdir(parents=True, exist_ok=True)
        arguments.sortie.write_text(json.dumps(jeu, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(jeu)} questions : {arguments.sortie}")
        return

    jeu = json.loads(arguments.jeu.read_text(encoding="utf-8"))
    if arguments.commande == "jouer":
        from app.services.recherche_approfondie import LOT_LECTURE

        formulations = (
            json.loads(arguments.formulations.read_text(encoding="utf-8"))
            if arguments.formulations
            else {}
        )

        async def tout() -> list[dict[str, Any]]:
            resultats = []
            for entree in jeu:
                print(f"... {entree['question'][:70]}", flush=True)
                resultats.append(
                    await jouer_question(
                        entree,
                        sans=set(arguments.sans),
                        suivi=not arguments.sans_suivi,
                        lot=arguments.lot or LOT_LECTURE,
                        formulations=formulations,
                    )
                )
            return resultats

        _ecrire(arguments.sortie, "philum", asyncio.run(tout()))
        return

    externe = json.loads(arguments.externe.read_text(encoding="utf-8"))

    async def noter_tout() -> list[dict[str, Any]]:
        return [await noter_externe(e, externe.get(e["id"]) or []) for e in jeu]

    _ecrire(arguments.sortie, arguments.externe.stem, asyncio.run(noter_tout()))


if __name__ == "__main__":
    main()
