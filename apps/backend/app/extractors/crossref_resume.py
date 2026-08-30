"""Le resume depose par l'editeur chez Crossref, dernier recours de lecture.

Mesure du 2026-08-30, sur une session reelle. L'agent documentait l'effet
Warburg. Il a lu les metadonnees de ``10.1113/JP278810`` par ``get_url_metadata``,
qui lui a rendu le resume Crossref, et il a voulu en citer la premiere phrase :
« Contrary to Warburg's original thesis, accelerated aerobic glycolysis is not a
primary, permanent and universal consequence of dysfunctional [...] ». Refus, au
motif que « le texte de cette source n'a pu etre obtenu par aucune voie ».

Le passage etait exact, depose par l'editeur, et le serveur venait lui-meme de
l'afficher. Il etait refuse parce que la chaine de lecture ne consultait que des
etages qui rendent la *page*, et qu'aucun ne repondait ce jour-la. Le systeme
montrait donc une preuve d'une main et la declarait inexistante de l'autre. Le
modele a fait ce que fait un modele dans cette situation : il a boucle six fois,
puis il a propose a la personne de coller le passage elle-meme.

Un resume Crossref est depose par l'editeur, pas reconstitue : c'est du verbatim
au meme titre que le corps de l'article, et exactement la meme classe de preuve
que le resume PubMed que ``pmc_oracle`` sert deja pour les articles fermes.
D'ou cet etage, en dernier, apres tout ce qui rend le texte entier : un resume
ne remplace pas un article, il evite seulement de traiter en illisible une
source dont on tient noir sur blanc quelques centaines de mots.

Il est rendu avec ``complet=False``, ce qui suffit a ne pas mentir sur ce qu'on
a lu : un passage absent du resume n'est alors pas declare absent de la source,
il est declare non verifiable.

Le nettoyage JATS lui est propre, et c'est la raison d'etre du module.
``_parse_crossref_work`` remplace les balises par du vide, ce qui suffit a
afficher un resume mais colle les mots de part et d'autre d'une fin de
paragraphe (« ...du glucose.The Warburg... »). Un corpus d'ancrage ne supporte
pas cette soudure : ici les balises deviennent une espace.
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_OEUVRE = "https://api.crossref.org/works/{}"
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
_TIMEOUT = 15.0

_BALISE = re.compile(r"<[^>]+>")


def texte_du_resume(brut: str | None) -> str:
    """Rend un resume JATS comparable au texte d'une page.

    Les entites sont decodees apres le retrait des balises, jamais avant : dans
    l'autre ordre, un ``&lt;p&gt;`` ecrit litteralement dans le resume
    deviendrait une balise et serait efface alors qu'il fait partie du texte.
    """
    if not brut:
        return ""
    return " ".join(html.unescape(_BALISE.sub(" ", brut)).split())


async def texte_resume_crossref(doi: str | None) -> str:
    """Le resume d'un DOI chez Crossref, ou la chaine vide. Ne leve jamais.

    Tous les editeurs n'en deposent pas : Elsevier, entre autres, n'en depose
    aucun (verifie le 2026-08-30 sur ``10.1016/j.drup.2018.03.001``). L'absence
    est donc ordinaire et ne vaut pas incident.
    """
    if not doi:
        return ""
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            reponse = await client.get(_OEUVRE.format(quote(doi, safe="/")))
        if reponse.status_code != 200:
            return ""
        return texte_du_resume(reponse.json().get("message", {}).get("abstract"))
    except Exception as e:  # noqa: BLE001 — un etage de repli ne casse pas la lecture
        logger.debug("Crossref abstract lookup failed for doi=%s: %s", doi, e)
        return ""
