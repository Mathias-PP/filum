"""L'arbitre : quelles approches de recherche employer, et dans quel ordre.

Etude du 2026-09-14 : les meilleurs outils combinent des approches que Philum
n'a pas (corpus academiques par passages, suivi des citations, perspectives,
fusion de moteurs, requetes de contradiction). Les appliquer toutes a chaque
question couterait des quotas gratuits pour rien et noierait un petit modele :
une question sur le budget d'une commune n'a que faire d'Europe PMC, une
question sur un mecanisme biologique en a besoin d'abord.

L'arbitre decide a partir de signaux explicites (les mots de la question et de
ses sous-questions, ce qui est configure) et donne la raison de chaque choix.
Fonction pure : testable, reproductible, et sa decision s'ecrit telle quelle
dans la consigne de l'agent.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Ce qu'une approche apporte, dit au modele en une phrase.
APPROCHES = {
    "corpus_philum": "des fiches Philum portent peut-etre deja des extraits verifies sur ce sujet",
    "litterature": "OpenAlex cherche dans le texte integral de la litterature, toutes disciplines",
    "biomedical": "Europe PMC couvre la litterature biomedicale et son acces libre",
    "passages": "Semantic Scholar rend directement des passages du texte integral",
    "web": "la recherche web couvre institutions, presse, rapports et pages non academiques",
    "citants": "les articles qui citent une source pivot portent confirmations et contradictions recentes",
    "references": "les references d'une source pivot en donnent les fondements",
    "perspectives": "une question large se cherche sous plusieurs angles pour n'en oublier aucun",
    "contradiction": "une question debattue demande de chercher explicitement ce qui contredit",
    "fraicheur": "une question sur l'actualite se cherche d'abord sur le web, du plus recent au plus ancien",
}


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _motif(*mots: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(mots) + r")", re.IGNORECASE)


_BIOMEDICAL = _motif(
    "maladi",
    "patient",
    "sante",
    "medic",
    "clinique",
    "therap",
    "traitement",
    "symptom",
    "cancer",
    "vaccin",
    "virus",
    "bacteri",
    "infection",
    "gene",
    "genet",
    "cellul",
    "hormon",
    "neuro",
    "cerveau",
    "douleur",
    "syndrom",
    "diagnost",
    "epidemi",
    "nutrition",
    "endometri",
    "arthros",
    "diabet",
    "disease",
    "clinical",
    "health",
    "drug",
    "protein",
)
_SCIENTIFIQUE = _motif(
    "etude",
    "recherche",
    "scientifi",
    "mecanisme",
    "effet",
    "efficacite",
    "mesur",
    "experien",
    "donnees",
    "physique",
    "chimi",
    "biolog",
    "climat",
    "ecolog",
    "espece",
    "insecte",
    "materiau",
    "algorithm",
    "modele",
    "statisti",
    "psycholog",
    "cognit",
    "fusion",
    "plasma",
    "energie",
    "study",
    "evidence",
    "mechanism",
    "meta-analys",
)
_ACTUALITE = _motif(
    "actualite",
    "recemment",
    "cette annee",
    "aujourd",
    "en 202",
    "depuis 202",
    "derniere",
    "nouvelle loi",
    "election",
    "gouvernement actuel",
    "latest",
    "this year",
)
_DEBATTUE = _motif(
    "vraiment",
    "faut-il",
    "est-ce que",
    "mythe",
    "controvers",
    "debat",
    "polemi",
    "efficace",
    "dangereu",
    "risque",
    "vrai ou faux",
    "prouve",
    "scandale",
    "remet en cause",
)
_LARGE = _motif(
    "pourquoi",
    "comment",
    "impact",
    "consequences",
    "enjeux",
    "histoire",
    "societ",
    "politique",
    "economi",
    "droit",
    "juridi",
    "cultur",
    "evolution",
)


@dataclass(frozen=True)
class Approche:
    nom: str
    raison: str


@dataclass(frozen=True)
class Profil:
    biomedical: bool
    scientifique: bool
    actualite: bool
    debattue: bool
    large: bool


def profil(question: str, sous_questions: list[str]) -> Profil:
    """Ce que la question laisse voir d'elle-meme, sans modele."""
    texte = _sans_accents(" ".join([question, *sous_questions]))
    biomedical = bool(_BIOMEDICAL.search(texte))
    return Profil(
        biomedical=biomedical,
        scientifique=biomedical or bool(_SCIENTIFIQUE.search(texte)),
        actualite=bool(_ACTUALITE.search(texte)),
        debattue=bool(_DEBATTUE.search(texte)),
        large=bool(_LARGE.search(texte)) or len(sous_questions) >= 4,
    )


def strategie(
    question: str,
    sous_questions: list[str] | None = None,
    *,
    web_disponible: bool,
    passages_disponibles: bool,
) -> list[Approche]:
    """Les approches a employer pour cette question, dans l'ordre ou les appliquer."""
    p = profil(question, sous_questions or [])
    ordre: list[str] = ["corpus_philum"]

    if p.actualite and web_disponible:
        ordre += ["fraicheur", "web"]
    if p.scientifique:
        if passages_disponibles:
            ordre.append("passages")
        ordre.append("litterature")
        if p.biomedical:
            ordre.append("biomedical")
    if web_disponible and "web" not in ordre:
        ordre.append("web")
    if not p.scientifique:
        # Sans signal scientifique, la litterature reste utile en appoint : un
        # sujet d'histoire, de droit ou d'economie a aussi ses travaux.
        ordre.append("litterature")
    if p.large:
        ordre.append("perspectives")
    if p.debattue or p.scientifique:
        ordre += ["contradiction", "citants"]
    if p.scientifique:
        ordre.append("references")

    retenues: list[Approche] = []
    for nom in ordre:
        if all(a.nom != nom for a in retenues):
            retenues.append(Approche(nom, APPROCHES[nom]))
    return retenues


def familles_de_recherche(approches: list[Approche]) -> list[str]:
    """Les corpus a interroger, dans l'ordre, pour l'outil `chercher_sources`."""
    corpus = ("corpus_philum", "passages", "litterature", "biomedical", "web")
    return [a.nom for a in approches if a.nom in corpus]


def bloc_strategie(approches: list[Approche]) -> str:
    """La decision de l'arbitre, telle qu'elle est dite au modele."""
    lignes = [f"{rang}. {a.nom} : {a.raison}" for rang, a in enumerate(approches, start=1)]
    return "Stratégie de recherche retenue pour cette question, dans l'ordre :\n" + "\n".join(
        lignes
    )
