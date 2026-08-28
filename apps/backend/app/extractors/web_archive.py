"""Lire une page par l'archive du web, quel que soit son domaine.

Les autres extracteurs de ce dossier repondent chacun a un hebergeur :
``pmc_oracle`` a NCBI, ``wikipedia_oracle`` a Wikipedia, ``europepmc_oracle``
au sous-ensemble libre de la litterature biomedicale. Empiles, ils elargissent
la couverture ; ils ne la garantissent nulle part. Une page de presse, un blog,
un rapport d'ONG bloques par un Cloudflare ne relevaient d'aucun d'eux.

Cette route-ci ne connait aucun domaine. Elle demande a l'archive du web ce
qu'elle a capture, et lit sa capture. Ce qui est publiquement archive est
lisible, que l'editeur reponde ou non aujourd'hui, depuis n'importe quelle IP.

**Pourquoi c'est le manque et non le site qui bloque.** Mesure du 2026-08-28 :
``molmed.biomedcentral.com/articles/10.1186/s10020-025-01205-6`` rend 807 793
octets en HTTP 200 depuis un poste ordinaire, et echouait en production. Le
refus suit la reputation de l'IP -- la VM est sur une plage GCP massivement
filtree -- pas l'URL. Une route servie par l'infrastructure d'archive.org
change d'origine, et c'est la ce qui la rend generale : 108 780 caracteres de
ce meme article rendus par la capture du 2025-08-16.

Deux limites, assumees : l'archive rend l'etat d'un jour, pas celui
d'aujourd'hui, et elle ne rend rien de ce qui n'a jamais ete capture. Un
extrait verifie par ici l'est contre une version datee, ce que l'horodatage de
la capture permet de dire.
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from app.core.url_safety import SAFE_REDIRECT_HOOKS
from app.services.wayback import resoudre_redirections, strip_tracking_params

logger = logging.getLogger(__name__)

_CDX = "https://web.archive.org/cdx/search/cdx"
#: Second canal sur le meme index, limite et servi independamment du premier.
#: Mesure du 2026-08-28, trois lectures de suite de la meme URL : CDX a rendu
#: un ``ReadTimeout`` a la premiere et la capture aux deux suivantes. Un seul
#: canal fait donc echouer une lecture sur trois, sur une page qui est
#: parfaitement archivee.
_DISPONIBILITE = "https://archive.org/wayback/available"
#: ``id_`` demande le document tel qu'il a ete capture, sans la banniere de
#: rejeu ni les scripts que l'archive injecte. Sans ce drapeau, le texte rendu
#: melange l'article et le chrome d'archive.org.
_CAPTURE = "https://web.archive.org/web/{}id_/{}"
_HEADERS = {
    "User-Agent": "Philum/0.1 (https://github.com/Mathias-PP/filum; mailto:contact@philum.app)"
}
#: CDX cherche dans un index de centaines de milliards de captures : mesures
#: repetees depuis la VM entre 18 et 20 secondes pour une requete qui ne rend
#: rien. Un timeout court ne conclurait pas « pas de capture », il ne
#: conclurait rien. La valeur est celle que le service d'archivage a retenue
#: apres la meme mesure.
_TIMEOUT_INDEX = 60.0
_TIMEOUT_CAPTURE = 30.0
_TIMEOUT_RESOLUTION = 15.0

#: En dessous, ce n'est pas un article. Une capture de page de redirection ou
#: de mur de consentement repond 200 avec quelques dizaines de caracteres, et
#: la rendre ferait chercher au modele un extrait dans un texte qui n'en
#: contient aucun -- exactement la situation ou il en invente un.
_TAILLE_MINIMALE = 200


async def _json(endpoint: str, params: dict[str, str], url: str):
    """Le JSON d'un canal, ou None s'il n'a pas repondu.

    Panne, timeout et reponse illisible sont regroupes a dessein : aucun ne dit
    « pas de capture ». Ils disent « pas de reponse », et c'est a l'appelant
    d'essayer l'autre canal plutot que de conclure a une absence.
    """
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT_INDEX) as client:
            reponse = await client.get(endpoint, params=params)
        if reponse.status_code != 200:
            return None
        return reponse.json()
    except Exception as e:  # noqa: BLE001 -- une route de repli ne fait jamais echouer l'appelant.
        # Le type et pas seulement le message : un `ReadTimeout` a un message
        # vide, et sans son nom le journal n'apprend rien a qui cherche.
        logger.info("Index %s muet pour %s : %s %s", endpoint, url, type(e).__name__, e)
        return None


async def _par_cdx(url: str) -> tuple[str, str] | None:
    """L'index CDX. ``limit=-1`` demande la derniere capture et non la
    premiere : la premiere capture d'une revue peut preceder de dix ans
    l'article qu'on cherche. ``statuscode:200`` ecarte les captures de
    redirections, qui ne preservent aucun contenu."""
    lignes = await _json(
        _CDX,
        {
            "url": url,
            "output": "json",
            "limit": "-1",
            "filter": "statuscode:200",
            "fl": "timestamp,original",
        },
        url,
    )
    # CDX rend une matrice dont la premiere ligne est l'en-tete, et une liste
    # vide quand il n'a rien. Un HTML d'erreur servi en 200 n'est ni l'un ni
    # l'autre : on ne s'en sert pas pour conclure a une absence.
    if not isinstance(lignes, list) or len(lignes) < 2 or not isinstance(lignes[1], list):
        return None
    horodatage, originale = str(lignes[1][0]), str(lignes[1][1])
    return _CAPTURE.format(horodatage, originale), horodatage


async def _par_disponibilite(url: str) -> tuple[str, str] | None:
    """L'API `wayback/available`. Elle rend la capture la plus proche d'un
    horodatage et non la derniere, ce qui suffit ici : elle n'intervient que
    quand CDX n'a pas repondu, et une capture datee vaut mieux qu'aucune."""
    charge = await _json(_DISPONIBILITE, {"url": url}, url)
    if not isinstance(charge, dict):
        return None
    capture = (charge.get("archived_snapshots") or {}).get("closest") or {}
    horodatage = str(capture.get("timestamp") or "")
    if not capture.get("url") or not horodatage:
        return None
    return _CAPTURE.format(horodatage, url), horodatage


async def derniere_capture(url: str) -> tuple[str, str] | None:
    """(url de la capture la plus recente, horodatage), ou None.

    Deux canaux interrogent le meme index, et la limitation porte sur le point
    d'entree et non sur l'archive : s'arreter au premier silence reviendrait a
    conclure « jamais archivee » sans avoir regarde.
    """
    for canal in (_par_cdx, _par_disponibilite):
        trouve = await canal(url)
        if trouve is not None:
            return trouve
    return None


def texte_de_la_capture(html: str) -> str | None:
    """Le texte d'une capture, ou None si elle ne porte pas d'article.

    Le detecteur d'obstacle de ``url_extractor`` est rejoue ici : l'archive a
    parfois capture le defi anti-robot plutot que la page, et rendre « Un
    instant, verification de votre navigateur » comme corps d'article ferait
    conclure au modele que l'article ne dit rien.
    """
    from app.extractors.url_extractor import _looks_like_challenge_page

    soup = BeautifulSoup(html, "lxml")
    balise = soup.find("title")
    titre = balise.get_text(strip=True) if balise else None
    texte = soup.get_text(separator=" ", strip=True)
    if _looks_like_challenge_page(titre, texte):
        return None
    return texte if len(texte) >= _TAILLE_MINIMALE else None


async def texte_archive(url: str | None) -> str | None:
    """L'URL lue dans l'archive du web, ou None. Ne leve jamais.

    L'URL est resolue avant d'etre cherchee : l'archive d'un resolveur
    (``doi.org``, un raccourcisseur, un « linking hub » d'editeur) n'a que des
    captures de redirection. Mesure du 2026-08-28 :
    ``doi.org/10.2174/1871520616666161031143301`` n'a aucune capture en 200,
    sa cible ``eurekaselect.com/article/79409`` en a une.

    ``None`` ne dit pas « page perdue » : il couvre aussi une page jamais
    capturee et un archive.org injoignable.
    """
    propre = (url or "").strip()
    if not propre:
        return None
    # Un parametre de suivi ne designe pas la ressource, et CDX cherche l'URL
    # exacte : `…/article?utm_source=x` et `…/article` sont deux cles, seule la
    # seconde a une capture.
    cible = strip_tracking_params(
        await resoudre_redirections(propre, _TIMEOUT_RESOLUTION) or propre
    )
    capture = await derniere_capture(cible)
    if capture is None:
        return None
    adresse, horodatage = capture
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT_CAPTURE,
            follow_redirects=True,
            event_hooks=SAFE_REDIRECT_HOOKS,
        ) as client:
            reponse = await client.get(adresse)
    except Exception as e:  # noqa: BLE001 -- idem : jamais d'exception vers l'appelant.
        logger.info("Capture illisible pour %s : %s %s", adresse, type(e).__name__, e)
        return None
    if reponse.status_code != 200 or "html" not in reponse.headers.get("content-type", ""):
        return None
    texte = texte_de_la_capture(reponse.text)
    if texte:
        logger.info("Lu par l'archive url=%s capture=%s", cible, horodatage)
    return texte
