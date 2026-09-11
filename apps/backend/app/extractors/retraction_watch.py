"""Le motif d'une retractation, tel que Retraction Watch le formule.

Crossref dit qu'un article est retracte, jamais pourquoi : son champ
``updated-by`` porte le DOI de l'avis, son type et sa date, rien d'autre
(verifie le 2026-09-11 sur le papier Wakefield, ``10.1016/S0140-6736(97)11096-0``).
Le motif vit uniquement dans le jeu Retraction Watch, que Crossref publie en un
seul fichier CSV, sans interrogation par DOI : un appel rend les 72 000 lignes
ou rien.

Or le motif change ce que le createur doit faire.
« Falsification/Fabrication of Data » retire la citation ; « Duplication of/in
Article » ne dit rien des resultats ; « Notice - Limited or No Information » dit
que l'avis lui-meme ne dit rien.

**Philum ne classe pas ces motifs.** Le vocabulaire est celui de Retraction
Watch, il est rendu tel quel et attribue, et c'est le createur qui juge. Graduer
les 112 motifs observes en trois niveaux de gravite reviendrait a porter, depuis
une table ecrite ici, un jugement sur la conduite de chercheurs nommes. C'est la
meme regle qu'ailleurs dans le projet : le resolveur fait foi, Philum rapporte.

Licence : Crossref publie ce jeu sous CC BY 4.0. L'attribution se fait partout
ou le motif s'affiche.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.extractors.retraction import RetractionStatus

logger = logging.getLogger(__name__)

#: Le fichier fait environ 66 Mo et met une quinzaine de secondes a arriver.
#: Un timeout aligne sur celui de `retraction.py` (10 s) le couperait toujours.
_TIMEOUT = 180.0

#: Deux adresses pour le meme fichier, essayees dans cet ordre.
#:
#: Le miroir GitLab passe en premier parce qu'il tient debout. Mesure le
#: 2026-09-11, depuis la VM et depuis un poste : le point d'acces Labs rendait
#: 502 en 0,4 s et 504 apres 37 s, quand le miroir rendait 200 et 66 537 343
#: octets. Labs est un bac a sable que Crossref ne s'engage pas a maintenir ;
#: le depot git est la forme que Crossref documente pour une copie locale, et
#: il recoit la meme mise a jour quotidienne.
#:
#: Labs reste en second, non par symetrie mais parce que les deux tombent pour
#: des raisons differentes : une panne de GitLab n'est pas une panne de
#: Crossref. Garder les deux, c'est ne dependre d'aucun des deux.
_URLS = (
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    # L'adresse de courriel est le seul parametre attendu, nue, sans nom de
    # cle : c'est la forme documentee par Crossref pour ce point d'acces.
    "https://api.labs.crossref.org/data/retractionwatch?contact@philum.app",
)

# Les natures observees dans le jeu, au 2026-09-11 : Retraction (66869),
# Expression of concern (3715), Correction (1514), vide (218),
# Reinstatement (160).
#
# `Reinstatement` est volontairement absent. Une reinstallation annule un avis
# anterieur ; l'attacher comme motif a un article que Crossref dit retracte
# afficherait « retracte, motif : reinstallation », ce qui ne veut rien dire.
# Le statut vient de Crossref et lui seul ; ce module ne fait qu'y coller le
# motif correspondant.
_NATURES: dict[str, RetractionStatus] = {
    "retraction": RetractionStatus.RETRACTED,
    "expression of concern": RetractionStatus.CONCERN,
    "correction": RetractionStatus.CORRECTED,
}


@dataclass(frozen=True)
class AvisRetractionWatch:
    #: DOI de l'article d'origine, en minuscules : 16 196 lignes sur 72 476 le
    #: portent avec des majuscules, et un DOI est insensible a la casse.
    doi: str
    statut: RetractionStatus
    #: Liste de tags separes par des points-virgules, dans le vocabulaire
    #: controle de Retraction Watch. Rendue verbatim, jamais reformulee.
    motif: str
    date_avis: date | None


def _date_americaine(brut: str) -> date | None:
    """`5/5/2026 0:00` vers une date. Rend `None` sur tout le reste.

    Le mois precede le jour dans ce jeu. Une date illisible ne vaut pas une
    date fausse : elle vaut rien, et le tri la place en dernier.
    """
    texte = (brut or "").strip()
    if not texte:
        return None
    try:
        return datetime.strptime(texte.split(" ")[0], "%m/%d/%Y").date()
    except ValueError:
        return None


def parser_dump(contenu: str) -> dict[str, list[AvisRetractionWatch]]:
    """Indexe le CSV par DOI d'article d'origine. Fonction pure.

    Un meme article peut porter plusieurs avis : le papier Wakefield a une
    correction en 2004 puis une retractation en 2010. Les deux sont conserves,
    le choix se fait dans `motif_pour`.
    """
    index: dict[str, list[AvisRetractionWatch]] = {}
    for ligne in csv.DictReader(io.StringIO(contenu)):
        doi = (ligne.get("OriginalPaperDOI") or "").strip().lower()
        motif = (ligne.get("Reason") or "").strip()
        statut = _NATURES.get((ligne.get("RetractionNature") or "").strip().lower())
        if not doi or not motif or statut is None:
            continue
        index.setdefault(doi, []).append(
            AvisRetractionWatch(
                doi=doi,
                statut=statut,
                motif=motif,
                date_avis=_date_americaine(ligne.get("RetractionDate") or ""),
            )
        )
    return index


def motif_pour(avis: list[AvisRetractionWatch], statut: str | None) -> str | None:
    """Le motif du plus recent avis dont la nature correspond au statut retenu.

    Le filtre sur le statut n'est pas un detail : un article retracte en 2010
    apres une correction en 2004 afficherait sinon le motif de la correction
    sous le badge « retracte ». Aucun avis de la bonne nature vaut `None`,
    c'est-a-dire un silence, jamais un motif approchant.
    """
    correspondants = [a for a in avis if a.statut.value == statut]
    if not correspondants:
        return None
    # `date.min` place les dates illisibles derriere celles qu'on sait lire,
    # sans les ecarter : un motif date d'inconnu vaut mieux que pas de motif.
    return max(correspondants, key=lambda a: a.date_avis or date.min).motif


async def telecharger_dump() -> dict[str, list[AvisRetractionWatch]] | None:
    """Recupere et indexe le jeu complet. Ne leve jamais, rend `None` si echec.

    Essaie chaque adresse de `_URLS` et s'arrete a la premiere qui repond. Un
    echec n'a pas a interrompre l'appelant : les motifs sont un complement, et
    une passe qui n'en pose aucun laisse le corpus exactement dans l'etat ou
    elle l'a trouve.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        for url in _URLS:
            try:
                reponse = await client.get(url)
            except Exception as e:
                logger.warning("Retraction Watch injoignable sur %s : %s", url, e)
                continue
            if reponse.status_code != 200:
                logger.warning("Retraction Watch a repondu %s sur %s", reponse.status_code, url)
                continue
            return parser_dump(reponse.text)
    return None
