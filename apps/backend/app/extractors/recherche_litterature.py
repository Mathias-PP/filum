"""Chercher des articles et des passages dans les corpus academiques ouverts.

Mesure du 2026-09-14 : le seul moteur de l'agent etait une recherche web
generale. Les systemes les mieux notes pour citer juste (Ai2 Scholar QA,
OpenScholar, PaperQA2) cherchent d'abord dans la litterature, au niveau du
passage, et suivent les references. Ce module donne a l'agent trois corpus
ouverts et le graphe des citations :

- OpenAlex : recherche plein texte sur les travaux (0,001 $ l'appel, dans le
  dollar quotidien gratuit de la cle), references et articles citants ;
- Europe PMC : litterature biomedicale, sans cle, avec l'acces libre ;
- Semantic Scholar : passages extraits du texte integral, quand une cle est
  configuree (l'acces anonyme repond 429).

Chaque fonction rend des candidates et ne leve jamais : un corpus en panne
n'empeche pas les autres.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.extractors.openalex_client import entetes_openalex

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_UA = {"User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"}
_OPENALEX = "https://api.openalex.org/works"
_EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_S2_PASSAGES = "https://api.semanticscholar.org/graph/v1/snippet/search"
_CHAMPS_OPENALEX = (
    "id,doi,display_name,publication_year,cited_by_count,type,open_access,"
    "primary_location,authorships"
)
#: Meme plafond que les metadonnees : une liste de trente noms n'aide personne.
_MAX_AUTEURS = 5


@dataclass
class Candidate:
    """Une source possible, avant exploration : ou la lire, et ce qu'on en sait."""

    url: str
    titre: str | None
    famille: str
    sources: list[str] = field(default_factory=list)
    annee: int | None = None
    doi: str | None = None
    auteurs: str | None = None
    revue: str | None = None
    citations: int | None = None
    acces_libre_url: str | None = None
    type: str | None = None
    #: Passage verbatim quand le corpus le rend (Semantic Scholar).
    passage: str | None = None
    #: Apercu d'un moteur web : ni verbatim garanti, ni citable tel quel.
    apercu: str | None = None
    raisons: list[str] = field(default_factory=list)

    def en_dict(self) -> dict[str, object]:
        return {
            cle: valeur
            for cle, valeur in {
                "url": self.url,
                "titre": self.titre,
                "famille": self.famille,
                "sources": self.sources,
                "annee": self.annee,
                "doi": self.doi,
                "auteurs": self.auteurs,
                "revue": self.revue,
                "citations": self.citations,
                "acces_libre_url": self.acces_libre_url,
                "type": self.type,
                "passage": self.passage,
                "apercu": self.apercu,
                "raison": " ; ".join(self.raisons) or None,
            }.items()
            if valeur not in (None, [], "")
        }


async def _get_json(url: str, *, params: dict | None = None, entetes: dict | None = None):
    try:
        async with httpx.AsyncClient(
            headers={**_UA, **(entetes or {})}, timeout=_TIMEOUT
        ) as client:
            reponse = await client.get(url, params=params)
    except Exception as e:  # noqa: BLE001 -- un corpus muet ne fait jamais echouer l'agent
        logger.info("Corpus injoignable %s : %s %s", url, type(e).__name__, e)
        return None
    if reponse.status_code != 200:
        logger.info("Corpus %s a repondu %s", url, reponse.status_code)
        return None
    try:
        return reponse.json()
    except ValueError:
        return None


def _doi_nu(doi: str | None) -> str | None:
    propre = (doi or "").strip().lower()
    propre = propre.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return propre or None


def candidate_openalex(work: dict) -> Candidate | None:
    """Un travail OpenAlex en candidate. Fonction pure."""
    titre = (work.get("display_name") or "").strip()
    if not titre:
        return None
    doi = _doi_nu(work.get("doi"))
    emplacement = work.get("primary_location") or {}
    url = f"https://doi.org/{doi}" if doi else (emplacement.get("landing_page_url") or "")
    if not url:
        return None
    acces = work.get("open_access") or {}
    noms = [
        nom
        for a in (work.get("authorships") or [])[:_MAX_AUTEURS]
        if (nom := ((a.get("author") or {}).get("display_name") or "").strip())
    ]
    return Candidate(
        url=url,
        titre=titre,
        famille="litterature",
        sources=["openalex"],
        annee=work.get("publication_year"),
        doi=doi,
        auteurs=", ".join(noms) or None,
        revue=((emplacement.get("source") or {}).get("display_name")),
        citations=work.get("cited_by_count"),
        acces_libre_url=acces.get("oa_url") or None,
        type=work.get("type"),
    )


def candidate_europepmc(resultat: dict) -> Candidate | None:
    """Un resultat Europe PMC en candidate. Fonction pure."""
    titre = (resultat.get("title") or "").strip()
    if not titre:
        return None
    doi = _doi_nu(resultat.get("doi"))
    pmcid = (resultat.get("pmcid") or "").strip()
    pmid = (resultat.get("pmid") or "").strip()
    if doi:
        url = f"https://doi.org/{doi}"
    elif pmcid:
        url = f"https://europepmc.org/article/PMC/{pmcid.removeprefix('PMC')}"
    elif pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        return None
    libre = resultat.get("isOpenAccess") == "Y" and pmcid
    types = ((resultat.get("pubTypeList") or {}).get("pubType")) or []
    brut_citations = resultat.get("citedByCount")
    brut_annee = resultat.get("pubYear")
    try:
        citations = int(str(brut_citations)) if brut_citations else None
        annee = int(str(brut_annee)) if brut_annee else None
    except ValueError:
        citations, annee = None, None
    return Candidate(
        url=url,
        titre=titre,
        famille="biomedical",
        sources=["europepmc"],
        annee=annee,
        doi=doi,
        auteurs=(resultat.get("authorString") or None),
        revue=(resultat.get("journalTitle") or None),
        citations=citations,
        acces_libre_url=f"https://europepmc.org/article/PMC/{pmcid.removeprefix('PMC')}"
        if libre
        else None,
        type=", ".join(str(t) for t in types) or None,
    )


def candidate_passage_s2(correspondance: dict) -> Candidate | None:
    """Un passage Semantic Scholar en candidate. Fonction pure.

    Forme relevee le 2026-09-14 dans la description OpenAPI de l'API :
    `{snippet: {text, snippetKind, section}, score, paper: {corpusId, title,
    authors, openAccessInfo}}`. Le passage ne porte pas de DOI : l'adresse est
    celle que Semantic Scholar resout depuis l'identifiant de corpus.
    """
    passage = correspondance.get("snippet") or {}
    papier = correspondance.get("paper") or {}
    texte = (passage.get("text") or "").strip()
    titre = (papier.get("title") or "").strip()
    corpus_id = str(papier.get("corpusId") or "").strip()
    if not texte or not titre or not corpus_id:
        return None
    noms = []
    for auteur in (papier.get("authors") or [])[:_MAX_AUTEURS]:
        nom = auteur.get("name") if isinstance(auteur, dict) else auteur
        if isinstance(nom, str) and nom.strip():
            noms.append(nom.strip())
    acces = papier.get("openAccessInfo") or {}
    section = passage.get("section") or passage.get("snippetKind")
    return Candidate(
        url=f"https://api.semanticscholar.org/CorpusId:{corpus_id}",
        titre=titre,
        famille="litterature",
        sources=["semantic_scholar"],
        auteurs=", ".join(noms) or None,
        acces_libre_url=(acces.get("url") if isinstance(acces, dict) else None) or None,
        passage=texte,
        raisons=[f"passage de la section « {section} »"] if section else [],
    )


async def chercher_openalex(requete: str, *, limite: int = 10) -> list[Candidate]:
    """Travaux dont le titre, le resume ou le texte integral repondent a la requete."""
    charge = await _get_json(
        _OPENALEX,
        params={"search": requete, "per_page": limite, "select": _CHAMPS_OPENALEX},
        entetes=entetes_openalex(),
    )
    travaux = (charge or {}).get("results") or []
    return [c for w in travaux if isinstance(w, dict) and (c := candidate_openalex(w))]


async def chercher_europepmc(requete: str, *, limite: int = 10) -> list[Candidate]:
    """Articles biomedicaux, resumes compris, avec leur acces libre."""
    charge = await _get_json(
        _EUROPEPMC,
        params={"query": requete, "format": "json", "pageSize": limite, "resultType": "core"},
    )
    resultats = ((charge or {}).get("resultList") or {}).get("result") or []
    return [c for r in resultats if isinstance(r, dict) and (c := candidate_europepmc(r))]


def s2_disponible() -> bool:
    return bool(get_settings().semantic_scholar_api_key.strip())


async def chercher_passages_s2(requete: str, *, limite: int = 10) -> list[Candidate]:
    """Passages du texte integral qui repondent a la requete. Vide sans cle."""
    cle = get_settings().semantic_scholar_api_key.strip()
    if not cle:
        return []
    charge = await _get_json(
        _S2_PASSAGES,
        params={"query": requete, "limit": limite},
        entetes={"x-api-key": cle},
    )
    correspondances = (charge or {}).get("data") or []
    return [c for m in correspondances if isinstance(m, dict) and (c := candidate_passage_s2(m))]


#: Plus grande page que rend OpenAlex : un voisinage tient en un appel par sens.
PAGE_OPENALEX = 200

#: Un filtre OpenAlex accepte jusqu'a 100 identifiants separes par « | ».
_IDENTIFIANTS_PAR_FILTRE = 100


async def voisinage_openalex(
    doi: str, *, sens: str, limite: int = PAGE_OPENALEX
) -> list[Candidate]:
    """Les references d'un article (`references`) ou les articles qui le citent (`citants`).

    Les citants sont tries du plus recent au plus ancien : c'est la ou vivent les
    confirmations, les nuances et les contradictions posterieures a l'article.
    Les references sont triees par citations : ce sont les fondements. Toutes
    les references sont demandees, par paquets de cent identifiants : une revue
    en cite souvent davantage, et les tronquer perdait des fondements au hasard.
    """
    propre = _doi_nu(doi)
    if not propre or sens not in ("references", "citants"):
        return []
    travail = await _get_json(
        f"{_OPENALEX}/doi:{quote(propre, safe='/')}",
        params={"select": "id,referenced_works"},
        entetes=entetes_openalex(),
    )
    if not travail or not travail.get("id"):
        return []
    identifiant = str(travail["id"]).rsplit("/", 1)[-1]
    if sens == "citants":
        filtres, tri = [f"cites:{identifiant}"], "publication_date:desc"
    else:
        references = [str(w).rsplit("/", 1)[-1] for w in (travail.get("referenced_works") or [])]
        filtres = [
            "openalex_id:" + "|".join(references[debut : debut + _IDENTIFIANTS_PAR_FILTRE])
            for debut in range(0, len(references), _IDENTIFIANTS_PAR_FILTRE)
        ]
        tri = "cited_by_count:desc"
    travaux: list[dict] = []
    for filtre in filtres:
        charge = await _get_json(
            _OPENALEX,
            params={"filter": filtre, "sort": tri, "per_page": limite, "select": _CHAMPS_OPENALEX},
            entetes=entetes_openalex(),
        )
        travaux += [w for w in (charge or {}).get("results") or [] if isinstance(w, dict)]
    if len(filtres) > 1:
        travaux.sort(key=lambda w: w.get("cited_by_count") or 0, reverse=True)
    raison = "cite l'article pivot" if sens == "citants" else "cite par l'article pivot"
    candidates = []
    for w in travaux[:limite]:
        if c := candidate_openalex(w):
            c.raisons.append(raison)
            candidates.append(c)
    return candidates
