"""Acces libre a une reference, via OpenAlex.

Une bibliographie qui renvoie a un article sous paywall arrete le lecteur net.
Or une large part de ces articles a une version legalement gratuite ailleurs :
depot institutionnel, revue en libre acces, version acceptee sur HAL. OpenAlex
agrege ces routes et les expose sur ``works/doi:{doi}``.

Trois etats a ne jamais confondre, la meme regle que pour les retractations :

- **acces libre trouve** : une URL gratuite existe, on la donne ;
- **ferme** : OpenAlex connait la reference et ne trouve aucune version
  gratuite -- une information positive, datee ;
- **non verifiable** : pas de DOI, DOI inconnu d'OpenAlex, ou service
  injoignable. Afficher « payant » dans ce cas serait une affirmation que
  rien ne soutient, et pourrait detourner le lecteur d'une version libre
  qui existe.
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


class OpenAccessStatus(str, Enum):
    #: Revue integralement en libre acces, sans frais pour l'auteur.
    DIAMOND = "diamond"
    #: Revue en libre acces.
    GOLD = "gold"
    #: Version deposee dans une archive ouverte (HAL, arXiv, PubMed Central).
    GREEN = "green"
    #: Article libre dans une revue par ailleurs payante.
    HYBRID = "hybrid"
    #: Lisible gratuitement chez l'editeur, mais sans licence de reutilisation.
    BRONZE = "bronze"
    #: Libre d'acces par une route qu'OpenAlex nomme d'une facon inconnue ici.
    OPEN = "open"
    #: Verifie, aucune version gratuite connue.
    CLOSED = "closed"
    #: Verification impossible.
    UNVERIFIABLE = "unverifiable"


_KNOWN: dict[str, OpenAccessStatus] = {
    s.value: s for s in OpenAccessStatus if s is not OpenAccessStatus.OPEN
}


@dataclass
class OpenAccessResult:
    status: OpenAccessStatus
    #: Ou lire la version gratuite. `None` des que le statut n'est pas libre.
    url: str | None = None
    #: Licence declaree (« cc-by »...), quand elle est connue.
    license: str | None = None
    #: Revue referencee au DOAJ. `None` = inconnu, jamais « non » par defaut.
    in_doaj: bool | None = None


def classify_open_access(work: dict | None) -> OpenAccessResult:
    """Reduit une reponse OpenAlex a un verdict d'acces.

    Fonction pure : c'est elle qui porte la regle, le reseau n'est qu'un
    fournisseur de donnees.
    """
    if not work:
        return OpenAccessResult(status=OpenAccessStatus.UNVERIFIABLE)

    oa = work.get("open_access") or {}
    best = work.get("best_oa_location") or {}

    raw = str(oa.get("oa_status") or "").strip().lower()
    is_oa = bool(oa.get("is_oa"))

    if raw in _KNOWN:
        status = _KNOWN[raw]
    elif is_oa:
        # OpenAlex peut nommer une nouvelle route : « libre par une voie qu'on
        # ne sait pas nommer » reste vrai et utile, « ferme » serait faux.
        status = OpenAccessStatus.OPEN
    elif raw:
        status = OpenAccessStatus.CLOSED
    else:
        # Ni statut ni drapeau : la reponse ne dit rien de l'acces.
        return OpenAccessResult(status=OpenAccessStatus.UNVERIFIABLE)

    if status is OpenAccessStatus.CLOSED:
        # Un DOAJ connu reste une information meme sans version gratuite.
        return OpenAccessResult(
            status=status,
            in_doaj=_doaj_of(best),
        )

    # `oa_url` est le meilleur lien selon OpenAlex ; le PDF puis la page de
    # depot servent de repli. Un statut libre sans aucune URL ne serait pas
    # actionnable : on ne peut alors qu'annoncer l'acces, sans l'ouvrir.
    url = oa.get("oa_url") or best.get("pdf_url") or best.get("landing_page_url")

    return OpenAccessResult(
        status=status,
        url=str(url) if url else None,
        license=str(best.get("license")) if best.get("license") else None,
        in_doaj=_doaj_of(best),
    )


def _doaj_of(best_location: dict) -> bool | None:
    source = best_location.get("source") or {}
    value = source.get("is_in_doaj")
    return bool(value) if value is not None else None


async def check_open_access(doi: str | None) -> OpenAccessResult:
    """Interroge OpenAlex pour un DOI. Ne leve jamais.

    Retourne ``UNVERIFIABLE`` des que le doute est permis, plutot que de
    laisser croire a une verification qui n'a pas eu lieu.
    """
    cleaned = (doi or "").strip()
    if not cleaned:
        return OpenAccessResult(status=OpenAccessStatus.UNVERIFIABLE)
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(f"https://api.openalex.org/works/doi:{cleaned}")
        if r.status_code != 200:
            return OpenAccessResult(status=OpenAccessStatus.UNVERIFIABLE)
        work = r.json()
    except Exception as e:
        logger.debug("OpenAlex open-access check failed for doi=%s: %s", cleaned, e)
        return OpenAccessResult(status=OpenAccessStatus.UNVERIFIABLE)
    return classify_open_access(work)
