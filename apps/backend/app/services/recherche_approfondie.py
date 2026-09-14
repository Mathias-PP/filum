"""La recherche d'une sous-question : chercher large, lire, classer, suivre, s'arreter a saturation.

Etude du 2026-09-14 (meilleurs outils de recherche). Les gestes qui font la
qualite des meilleurs outils sont executes ici par le serveur, parce qu'un
modele, petit surtout, ne suit pas une methode decrite dans une consigne :

1. **Collecte large** (Gemini Deep Research, Consensus) : chaque formulation
   part vers tous les corpus configures, en parallele. Aucun tri a priori :
   ce sont les resultats qui tranchent.
2. **Fusion par rangs reciproques** : les classements des moteurs ne sont pas
   comparables entre eux, leurs rangs le sont.
3. **Lecture et passages** (Ai2 Scholar QA, OpenScholar) : chaque candidate est
   lue par la cascade de Philum, decoupee en passages, et chaque passage est
   compare par le sens a la sous-question et aux formulations de contradiction.
4. **Classement** : les sources sont rendues dans l'ordre de leur meilleur
   passage ; le modele lit ces passages et ne pose que ceux qui repondent. Il
   est le dernier etage du classement, dans toutes les langues.
5. **Suivi des citations et des liens** (PaperQA2, Undermind) : les sources
   pertinentes menent a ce qui les cite, a ce qu'elles citent et aux liens de
   leur corps de texte. Une source que plusieurs sources pertinentes designent
   remonte d'elle-meme par la fusion.
6. **Arret par saturation** (Undermind) : la lecture s'arrete quand un lot
   n'apporte aucune source pertinente nouvelle, les tours de suivi quand un tour
   n'en apporte aucune. La courbe des decouvertes dit ce qui reste probablement.

Rien ici ne depend d'une langue ni d'une formulation : ce qui demande de
comprendre la question (formulations, contradiction, jugement final) vient du
modele ; ce qui se compte (rangs, proximite de sens, nouveaute) se compte ici.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from uuid import uuid4

from app.extractors.recherche_litterature import Candidate
from app.services.fusion_candidates import fusionner, identite

logger = logging.getLogger(__name__)

Chercheur = Callable[[str], Awaitable[list[Candidate]]]

#: Candidates lues en parallele. Borne de concurrence reseau : chaque lecture
#: peut descendre la cascade entiere (page, NCBI, Europe PMC, relais, archive).
#: C'est aussi la fenetre d'arret d'un tour ; le banc de recherche en mesure
#: l'effet sur le rappel (`--lot`).
LOT_LECTURE = 6

#: Delai d'une recherche, en secondes. Borne technique : l'appel d'outil a son
#: propre budget (`TIMEOUTS_PAR_OUTIL`), et la boucle d'une etape son mur. Une
#: recherche qui l'atteint le dit, pour qu'une saturation ne soit jamais annoncee
#: a tort.
DELAI_RECHERCHE = 480.0

REPONSE = "reponse"
NUANCE = "nuance"


@dataclass(frozen=True)
class Passage:
    texte: str
    #: `reponse` : le passage eclaire la sous-question ; `nuance` : il repond a
    #: une formulation de contradiction.
    role: str
    #: Proximite de sens avec la question (embeddings).
    score: float
    #: La question que le passage eclaire le mieux.
    question: str = ""
    #: Jugement du reclasseur, quand il a pu passer sur toute la recherche.
    pertinence: float | None = None

    @property
    def classement(self) -> float:
        return self.pertinence if self.pertinence is not None else self.score


@dataclass
class SourceTrouvee:
    candidate: Candidate
    #: L'adresse effectivement lue : c'est elle que l'agent pose, pour que les
    #: passages se retrouvent dans la page au moment de la pose.
    url_lue: str
    passages: list[Passage]
    tour: int
    texte_complet: bool
    source_id: str | None = None
    retractation: str | None = None

    @property
    def meilleur(self) -> float:
        return max((p.classement for p in self.passages), default=0.0)

    def en_dict(self) -> dict[str, object]:
        c = self.candidate
        rendu: dict[str, object] = {
            "url": self.url_lue,
            "titre": c.titre,
            "doi": c.doi,
            "annee": c.annee,
            "type": c.type,
            "revue": c.revue,
            "auteurs": c.auteurs,
            "citations": c.citations,
            "acces_libre": bool(c.acces_libre_url) or None,
            "retractation": self.retractation,
            "trouvee_par": c.raisons or None,
            "moteurs": c.sources or None,
            "source_id": self.source_id,
            "texte_complet": self.texte_complet,
            "passages": [
                {
                    "texte": p.texte,
                    "role": p.role,
                    "score": p.score,
                    **({"pertinence": round(p.pertinence, 3)} if p.pertinence is not None else {}),
                }
                for p in self.passages
            ],
        }
        return {cle: valeur for cle, valeur in rendu.items() if valeur not in (None, [], "")}


@dataclass
class Journal:
    requetes: int = 0
    reponses_par_corpus: dict[str, int] = field(default_factory=dict)
    corpus_muets: list[str] = field(default_factory=list)
    candidates_vues: int = 0
    lues: int = 0
    illisibles: int = 0
    pertinentes_par_tour: list[int] = field(default_factory=list)
    #: Sources pertinentes cumulees apres chaque candidate lisible.
    courbe: list[int] = field(default_factory=list)
    arret: str = ""
    #: Le reclasseur qui a ordonne les passages, ou pourquoi il n'a pas servi.
    reclassement: str = ""
    duree_s: float = 0.0

    def en_dict(self) -> dict[str, object]:
        restantes = estimer_restantes(self.courbe)
        return {
            "requetes_envoyees": self.requetes,
            "reponses_par_corpus": self.reponses_par_corpus,
            "corpus_muets": self.corpus_muets or None,
            "candidates_vues": self.candidates_vues,
            "candidates_lues": self.lues,
            "candidates_illisibles": self.illisibles,
            "sources_pertinentes_par_tour": self.pertinentes_par_tour,
            "raison_de_l_arret": self.arret,
            "reclassement": self.reclassement or None,
            "sources_pertinentes_restantes_estimees": (
                round(restantes, 1) if restantes is not None else "saturation non visible"
            ),
            "duree_s": self.duree_s,
        }


@dataclass
class Recherche:
    id: str
    sous_question: str
    sources: list[SourceTrouvee]
    journal: Journal
    #: Identites de toutes les candidates vues, lues ou non : le banc y mesure ce
    #: que la collecte a trouve, avant ce que la lecture a retenu.
    vues: frozenset[str] = frozenset()


def estimer_restantes(courbe: list[int]) -> float | None:
    """Les sources pertinentes qui restent probablement a trouver. Fonction pure.

    Courbe de decouverte d'Undermind : apres n lectures, D(n) = N (1 - e^(-n/τ)).
    Methode des deux moities : avec a = D(m) et b = D(2m), b / a = 1 + e^(-m/τ),
    d'ou N = a / (2 - b / a). `None` quand rien n'a ete trouve, ou quand la
    seconde moitie a trouve autant que la premiere : la courbe ne ralentit pas
    encore, et aucune estimation honnete n'est possible.
    """
    moitie = len(courbe) // 2
    if moitie == 0:
        return None
    a, b = courbe[moitie - 1], courbe[2 * moitie - 1]
    if a == 0 or b >= 2 * a:
        return None
    total = a / (2 - b / a)
    return max(0.0, total - courbe[-1])


async def _web(requete: str) -> list[Candidate]:
    from app.agent_tools.web import rechercher_web_fusionne

    resultats, _repondu = await rechercher_web_fusionne(requete)
    return [
        Candidate(
            url=r["url"],
            titre=r.get("title") or None,
            famille="web",
            sources=(r.get("moteurs") or "web").split(","),
            apercu=r.get("snippet") or None,
        )
        for r in resultats
        if r.get("url")
    ]


def corpus_configures() -> dict[str, Chercheur]:
    """Tous les corpus que ce serveur sait interroger, sans choix a priori."""
    from app.agent_tools.web import fournisseurs_web
    from app.extractors import recherche_litterature as litterature

    corpus: dict[str, Chercheur] = {
        "openalex": litterature.chercher_openalex,
        "europepmc": litterature.chercher_europepmc,
    }
    if litterature.s2_disponible():
        corpus["semantic_scholar"] = litterature.chercher_passages_s2
    if fournisseurs_web():
        corpus["web"] = _web
    return corpus


def _adresses_a_lire(candidate: Candidate) -> list[str]:
    """Ou lire la candidate, dans l'ordre. Une adresse d'API ne se lit pas comme une page."""
    adresses = [candidate.url, candidate.acces_libre_url]
    lisibles = [a for a in adresses if a and "api.semanticscholar.org" not in a]
    return list(dict.fromkeys(lisibles))


async def _lire(
    candidate: Candidate, sous_question: str, contradictions: list[str]
) -> tuple[str, list[Passage], bool] | None:
    """L'adresse lue, les passages pertinents, et si le texte est entier ; None si illisible."""
    from app.services import excerpt_insertion
    from app.services.passages_candidats import proposer

    for adresse in _adresses_a_lire(candidate):
        try:
            texte, _refuse, complet = await excerpt_insertion.texte_de_page(adresse)
        except Exception:  # noqa: BLE001  # une page qui plante est une page illisible
            logger.info("Lecture impossible : %s", adresse, exc_info=True)
            continue
        if not texte.strip():
            continue
        questions = [sous_question, *contradictions]
        candidats = await proposer(texte, questions)
        passages = [
            Passage(
                c.texte,
                REPONSE if c.question == sous_question else NUANCE,
                c.score,
                question=c.question,
            )
            for c in candidats
        ]
        return adresse, passages, complet
    return None


class _Etat:
    def __init__(
        self,
        sous_question: str,
        contradictions: list[str],
        deja: Mapping[str, str],
        exclure: frozenset[str],
        lot: int,
        echeance: float,
    ) -> None:
        self.sous_question = sous_question
        self.contradictions = contradictions
        self.deja = deja
        self.vues: set[str] = set(exclure)
        self.pertinentes: dict[str, SourceTrouvee] = {}
        self.lot = max(1, lot)
        self.echeance = echeance
        self.journal = Journal()
        self.delai_atteint = False

    def nouvelles(self, candidates: list[Candidate]) -> list[Candidate]:
        retenues = []
        for candidate in candidates:
            cle = identite(candidate)
            if cle not in self.vues:
                self.vues.add(cle)
                retenues.append(candidate)
        self.journal.candidates_vues += len(retenues)
        return retenues

    async def explorer(self, candidates: list[Candidate], tour: int) -> list[SourceTrouvee]:
        """Lit les candidates par lots, jusqu'au premier lot lisible qui n'apporte rien."""
        trouvees: list[SourceTrouvee] = []
        for debut in range(0, len(candidates), self.lot):
            if time.monotonic() >= self.echeance:
                self.delai_atteint = True
                break
            lot = candidates[debut : debut + self.lot]
            lectures = await asyncio.gather(
                *(_lire(c, self.sous_question, self.contradictions) for c in lot),
                return_exceptions=True,
            )
            lisibles = 0
            nouvelles = 0
            for candidate, lecture in zip(lot, lectures, strict=True):
                self.journal.lues += 1
                if isinstance(lecture, BaseException) or lecture is None:
                    self.journal.illisibles += 1
                    continue
                lisibles += 1
                adresse, passages, complet = lecture
                cle = identite(candidate)
                if passages and cle not in self.pertinentes:
                    source = SourceTrouvee(
                        candidate=candidate,
                        url_lue=adresse,
                        passages=passages,
                        tour=tour,
                        texte_complet=complet,
                        source_id=self.deja.get(cle),
                    )
                    self.pertinentes[cle] = source
                    trouvees.append(source)
                    nouvelles += 1
                self.journal.courbe.append(len(self.pertinentes))
            if lisibles and not nouvelles:
                break
        self.journal.pertinentes_par_tour.append(len(trouvees))
        return trouvees


async def _voisins(sources: list[SourceTrouvee]) -> list[list[Candidate]]:
    """Ce que citent les sources pertinentes, ce qui les cite, et les liens de leurs pages."""
    from app.extractors import body_links, recherche_litterature
    from app.services.content_identity import extract_doi

    async def de(source: SourceTrouvee) -> list[list[Candidate]]:
        titre = source.candidate.titre or source.url_lue
        listes: list[list[Candidate]] = []
        doi = source.candidate.doi or extract_doi(source.url_lue)
        if doi:
            for sens, raison in (("citants", "cite"), ("references", "citee par")):
                voisins = await recherche_litterature.voisinage_openalex(doi, sens=sens)
                for voisin in voisins:
                    voisin.raisons = [f"{raison} « {titre} »"]
                listes.append(voisins)
        else:
            liens = await body_links.liens_de_la_page(source.url_lue)
            listes.append(
                [
                    Candidate(
                        url=lien.url,
                        titre=None,
                        famille="web",
                        sources=["lien"],
                        apercu=lien.raw_text,
                        raisons=[f"lien dans « {titre} »"],
                    )
                    for lien in liens
                ]
            )
        return listes

    reponses = await asyncio.gather(*(de(s) for s in sources), return_exceptions=True)
    return [liste for r in reponses if isinstance(r, list) for liste in r]


async def _reclasser(sources: list[SourceTrouvee]) -> str:
    """Reclasse tous les passages, question par question. Rend ce qui s'est passe, pour le journal.

    Tout ou rien : si une seule question echoue, aucun score du reclasseur n'est
    pose, sinon des sources jugees par deux echelles differentes seraient
    comparees entre elles.
    """
    from dataclasses import replace

    from app.services import reclassement

    if not reclassement.reclasseur_disponible():
        return "aucun reclasseur configure : ordre par proximite de sens"
    par_question: dict[str, list[tuple[int, int]]] = {}
    for rang_source, source in enumerate(sources):
        for rang_passage, passage in enumerate(source.passages):
            par_question.setdefault(passage.question, []).append((rang_source, rang_passage))
    pertinences: dict[tuple[int, int], float] = {}
    for question, places in par_question.items():
        textes = [sources[s].passages[p].texte for s, p in places]
        scores = await reclassement.reclasser(question, textes)
        if scores is None:
            return "reclasseur indisponible : ordre par proximite de sens"
        pertinences.update(zip(places, scores, strict=True))
    for rang_source, source in enumerate(sources):
        source.passages = [
            replace(passage, pertinence=pertinences[(rang_source, rang_passage)])
            for rang_passage, passage in enumerate(source.passages)
        ]
    return reclassement.MODELE_RECLASSEMENT


async def _retractations(sources: list[SourceTrouvee]) -> None:
    from app.extractors import retraction

    avec_doi = [s for s in sources if s.candidate.doi]
    verdicts = await asyncio.gather(
        *(retraction.check_retraction(s.candidate.doi) for s in avec_doi),
        return_exceptions=True,
    )
    for source, verdict in zip(avec_doi, verdicts, strict=True):
        if isinstance(verdict, BaseException):
            continue
        statut = verdict.status.value
        if statut not in ("none", "unverifiable"):
            source.retractation = statut


async def rechercher_sous_question(
    sous_question: str,
    requetes: list[str],
    requetes_contradiction: list[str],
    *,
    corpus: Mapping[str, Chercheur] | None = None,
    deja: Mapping[str, str] | None = None,
    exclure: frozenset[str] = frozenset(),
    expansion: bool = True,
    lot: int = LOT_LECTURE,
    delai: float = DELAI_RECHERCHE,
) -> Recherche:
    """La recherche complete d'une sous-question. Ne leve pas pour un corpus ou une page en panne.

    `deja` : identites (voir `fusion_candidates.identite`) des sources deja posees
    sur la fiche, vers leur identifiant. `exclure` : identites a ne jamais lire
    (le banc y met la revue dont les references servent de reference).
    """
    debut = time.monotonic()
    corpus = corpus if corpus is not None else corpus_configures()
    formulations = list(
        dict.fromkeys(q.strip() for q in [*requetes, *requetes_contradiction] if q.strip())
    )
    contradictions = [q.strip() for q in requetes_contradiction if q.strip()]
    etat = _Etat(sous_question, contradictions, deja or {}, exclure, lot, debut + delai)

    taches = [(nom, formulation) for formulation in formulations for nom in corpus]
    etat.journal.requetes = len(taches)
    reponses = await asyncio.gather(
        *(corpus[nom](formulation) for nom, formulation in taches), return_exceptions=True
    )
    listes: list[list[Candidate]] = []
    for (nom, formulation), reponse in zip(taches, reponses, strict=True):
        if isinstance(reponse, BaseException) or not isinstance(reponse, list):
            if nom not in etat.journal.corpus_muets:
                etat.journal.corpus_muets.append(nom)
            continue
        etat.journal.reponses_par_corpus[nom] = etat.journal.reponses_par_corpus.get(nom, 0) + len(
            reponse
        )
        for candidate in reponse:
            candidate.raisons.append(f"requete « {formulation} »")
        listes.append(reponse)

    tour = 1
    trouvees = await etat.explorer(etat.nouvelles(fusionner(listes)), tour)
    if not etat.journal.candidates_vues:
        etat.journal.arret = "aucune candidate : aucun corpus n'a rendu de resultat"
    elif not expansion:
        etat.journal.arret = "suivi des citations et des liens desactive"
    while expansion and trouvees and not etat.delai_atteint:
        tour += 1
        suivantes = etat.nouvelles(fusionner(await _voisins(trouvees)))
        if not suivantes:
            etat.journal.arret = f"tour {tour} : plus aucune candidate nouvelle a suivre"
            break
        trouvees = await etat.explorer(suivantes, tour)
        if not trouvees:
            etat.journal.arret = (
                f"saturation : le tour {tour} n'a apporte aucune source pertinente nouvelle"
            )
    if etat.delai_atteint:
        etat.journal.arret = (
            f"delai de {delai:.0f} s atteint au tour {tour} : la recherche n'a pas sature"
        )
    elif not etat.journal.arret:
        etat.journal.arret = "saturation : le premier tour n'a apporte aucune source pertinente"

    trouvees_toutes = list(etat.pertinentes.values())
    etat.journal.reclassement = await _reclasser(trouvees_toutes)
    for source in trouvees_toutes:
        source.passages.sort(key=lambda p: -p.classement)
    sources = sorted(trouvees_toutes, key=lambda s: (-s.meilleur, s.tour))
    await _retractations(sources)
    etat.journal.duree_s = round(time.monotonic() - debut, 1)
    return Recherche(
        id=uuid4().hex[:12],
        sous_question=sous_question,
        sources=sources,
        journal=etat.journal,
        vues=frozenset(etat.vues - exclure),
    )


def pages(sources: list[SourceTrouvee], budget: int) -> list[list[SourceTrouvee]]:
    """Les sources en pages d'environ `budget` caracteres, sans jamais couper une source. Fonction pure."""
    import json

    rendu: list[list[SourceTrouvee]] = []
    courante: list[SourceTrouvee] = []
    taille = 0
    for source in sources:
        poids = len(json.dumps(source.en_dict(), ensure_ascii=False))
        if courante and taille + poids > budget:
            rendu.append(courante)
            courante, taille = [], 0
        courante.append(source)
        taille += poids
    if courante:
        rendu.append(courante)
    return rendu


#: Recherches gardees pour `suite_recherche`, le temps d'une conversation. Un
#: seul processus uvicorn en production : la memoire du processus suffit.
_TTL_RECHERCHES = 3600.0

#: Borne en caracteres de passages gardes, meme raison que le cache des pages :
#: le conteneur est limite a 450 Mo.
_BUDGET_RECHERCHES = 2_000_000

_recherches: dict[str, tuple[float, Recherche]] = {}


def _poids(recherche: Recherche) -> int:
    return sum(len(p.texte) for s in recherche.sources for p in s.passages)


def garder(recherche: Recherche) -> None:
    maintenant = time.monotonic()
    for cle in [c for c, (t, _r) in _recherches.items() if maintenant - t >= _TTL_RECHERCHES]:
        del _recherches[cle]
    _recherches[recherche.id] = (maintenant, recherche)
    while (
        len(_recherches) > 1
        and sum(_poids(r) for _t, r in _recherches.values()) > _BUDGET_RECHERCHES
    ):
        _recherches.pop(next(iter(_recherches)))


def retrouver(recherche_id: str) -> Recherche | None:
    garde = _recherches.get(recherche_id)
    if garde is None or time.monotonic() - garde[0] >= _TTL_RECHERCHES:
        return None
    return garde[1]
