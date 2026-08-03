"""Avis de retractation, de mise en garde ou de correction, via Crossref.

Une bibliographie qui cite un article retracte le cite pour toujours : le
lecteur n'a aucun moyen de le savoir, et l'auteur de la fiche non plus une
fois la video publiee. Crossref agrege la base Retraction Watch et l'expose
sur ``works/{doi}`` dans le champ ``updated-by``.

Trois etats radicalement differents, qu'il ne faut jamais confondre :

- **avis trouve** : l'article a ete retracte, corrige, ou fait l'objet d'une
  mise en garde ;
- **aucun avis** : Crossref connait le DOI et ne signale rien -- une
  information positive, datee ;
- **non verifiable** : pas de DOI, DOI inconnu de Crossref, ou service
  injoignable. Afficher « aucune retractation » dans ce cas serait un
  mensonge par omission.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}


class RetractionStatus(str, Enum):
    NONE = "none"
    RETRACTED = "retracted"
    CONCERN = "concern"
    CORRECTED = "corrected"
    UNVERIFIABLE = "unverifiable"


# Un meme article peut porter plusieurs avis : une correction en 2004 puis une
# retractation en 2010. C'est le plus grave qui doit s'afficher, sans quoi le
# badge dirait « corrige » d'un article retracte depuis.
_SEVERITY: dict[RetractionStatus, int] = {
    RetractionStatus.NONE: 0,
    RetractionStatus.CORRECTED: 1,
    RetractionStatus.CONCERN: 2,
    RetractionStatus.RETRACTED: 3,
}

# Types Crossref observes dans `updated-by`. « withdrawal » et « removal »
# retirent l'article de la litterature aussi surement qu'une retractation :
# les distinguer dans l'interface n'apprendrait rien au lecteur.
_TYPE_MAP: dict[str, RetractionStatus] = {
    "retraction": RetractionStatus.RETRACTED,
    "partial_retraction": RetractionStatus.RETRACTED,
    "withdrawal": RetractionStatus.RETRACTED,
    "removal": RetractionStatus.RETRACTED,
    "expression_of_concern": RetractionStatus.CONCERN,
    "correction": RetractionStatus.CORRECTED,
    "erratum": RetractionStatus.CORRECTED,
    "corrigendum": RetractionStatus.CORRECTED,
}


@dataclass
class RetractionResult:
    status: RetractionStatus
    #: DOI de l'avis lui-meme, pour que le lecteur puisse aller le lire.
    notice_doi: str | None = None


def classify_updates(updates: list[dict] | None) -> RetractionResult:
    """Reduit le tableau ``updated-by`` de Crossref a un seul verdict.

    Fonction pure : c'est elle qui porte la regle, le reseau n'est qu'un
    fournisseur de donnees.
    """
    best = RetractionResult(status=RetractionStatus.NONE)
    for update in updates or []:
        mapped = _TYPE_MAP.get(str(update.get("type") or "").strip().lower())
        # Un type inconnu n'est pas un blanc-seing : Crossref peut en ajouter,
        # et « rien signale » serait alors faux. On le traite comme une mise en
        # garde, l'etat qui invite a verifier sans accuser.
        if mapped is None:
            if not update.get("type"):
                continue
            mapped = RetractionStatus.CONCERN
        if _SEVERITY[mapped] > _SEVERITY[best.status]:
            doi = update.get("DOI")
            best = RetractionResult(
                status=mapped,
                notice_doi=str(doi).lower() if doi else None,
            )
    return best


async def check_retraction(doi: str | None) -> RetractionResult:
    """Interroge Crossref pour un DOI. Ne leve jamais.

    Retourne ``UNVERIFIABLE`` des que le doute est permis -- pas de DOI, DOI
    inconnu, reseau muet -- plutot que de laisser croire a une verification
    qui n'a pas eu lieu.
    """
    cleaned = (doi or "").strip()
    if not cleaned:
        return RetractionResult(status=RetractionStatus.UNVERIFIABLE)
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(f"https://api.crossref.org/works/{cleaned}")
        if r.status_code != 200:
            return RetractionResult(status=RetractionStatus.UNVERIFIABLE)
        message = r.json().get("message") or {}
    except Exception as e:
        logger.debug("Crossref retraction check failed for doi=%s: %s", cleaned, e)
        return RetractionResult(status=RetractionStatus.UNVERIFIABLE)
    return classify_updates(message.get("updated-by"))
