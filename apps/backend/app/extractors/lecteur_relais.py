"""Lire une page depuis une autre origine que la notre, dans son etat du jour.

Ce module et ``web_archive`` repondent au meme constat et ne se remplacent pas.

Le constat, mesure le 2026-08-28 : l'article
``molmed.biomedcentral.com/articles/10.1186/s10020-025-01205-6`` rend 807 793
octets en HTTP 200 depuis un poste ordinaire et echouait en production. Le refus
suit la reputation de l'IP appelante, la VM etant sur une plage GCP massivement
filtree, et non l'URL demandee. Ce qui debloque n'est donc pas de mieux imiter
un navigateur depuis la meme machine, c'est de faire porter la requete par une
autre origine.

L'archive du web est une de ces origines, mais elle a deux manques que rien en
elle ne peut combler : elle rend l'etat d'un jour passe, et elle ne rend rien
d'une page jamais capturee. Un article publie ce matin, une page derriere un
Cloudflare qui a toujours tenu les robots d'archivage a distance, une URL avec
un parametre que l'index ne porte pas : aucune capture, donc aucune lecture.

Un relais de lecture n'a aucun de ces deux manques. Il va chercher la page
maintenant, et il n'a pas besoin qu'elle ait ete capturee un jour. Mesures du
2026-08-28, depuis la VM, sur trois pages que la lecture directe ne rendait pas :

===============================  ===========  ===========================
Page                             Octets       Ce que l'archive en donnait
===============================  ===========  ===========================
l'article Warburg ci-dessus       224 763      110 163, capture du 2025-08-16
un article du Monde                78 359      76 526, capture datee
un article ScienceDirect           11 475      rien
===============================  ===========  ===========================

D'ou l'ordre retenu dans la cascade : le relais passe **avant** l'archive, parce
qu'il rend l'etat courant, et l'archive reste derriere lui pour les cas ou le
relais lui-meme echoue (quota atteint, panne, page que le relais ne rend pas).

Un relais ne suffit pas, et c'est le point le plus contre-intuitif du module.
Mesures du 2026-08-28 depuis la VM, quatre tentatives consecutives : le relais
markdown rend le mur d'Elsevier a chaque fois, jamais l'article, donc reessayer
ne sert a rien. Il est aussi refuse d'office par ``x.com``, ou un second relais,
sur une autre origine, a rendu la page. Les angles morts ne se recouvrent pas :
d'ou une **chaine** de gabarits, essayes dans l'ordre, plutot qu'un point
d'entree unique. La chaine est configurable (``lecture_relais_endpoint``,
gabarits separes par des virgules) : le defaut marche sans clé ni inscription, ce
qui evite qu'une installation neuve soit muette, et un relais a rendu de page
s'ajoute en tete sans toucher au code le jour ou une barriere resiste au defaut.

Ce que la chaine ne peut pas faire, et il faut le dire ici pour qu'on cesse d'y
ajouter des origines en esperant l'inverse : un captcha ne se contourne pas en
changeant d'origine. Mesure du 2026-08-28 sur ``sciencedirect.com``, depuis une
IP residentielle ordinaire cette fois : HTTP 403, « Are you a robot? Please
confirm you are a human by completing the captcha challenge below », avec l'IP
appelante citee dans la page. Le refus ne vise donc plus une plage de
datacenter, il vise tout client qui n'execute pas le defi. Pour ces sites la
lecture passe par le contenu et non par l'origine : le DOI, puis un depot en
acces libre, ce que la cascade tente deja avant d'arriver ici. A defaut,
l'article est declare illisible, ce qui est la reponse juste.

Un relais rend soit du texte, soit du HTML brut. Le HTML est reduit a son texte
apres retrait des ``script`` et des ``style``, sans quoi la coquille que
ScienceDirect sert aux proxies, 167 601 octets dont l'essentiel est une police
en base64 dans une feuille de style, passerait pour un article de 166 919
caracteres.

Limite assumee, et elle est de nature differente des precedentes : l'URL demandee
est confiee a un tiers. Les sources d'une fiche Philum sont publiques par
construction, mais l'etage se desactive en vidant ``lecture_relais_endpoint``.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

#: Mesures du 2026-08-28 depuis la VM : 8,7 s et 11,1 s pour deux articles
#: complets. Le relais rend une page qu'il va chercher lui-meme, parfois en
#: rendant le JavaScript : sa latence est celle d'un navigateur, pas d'un GET.
_TIMEOUT = 45.0

#: Les relais suivants sont des replis, et un repli en panne ne doit pas couter
#: le meme temps qu'un relais qui travaille. Mesure du 2026-08-28 : le second
#: gabarit du defaut repondait 522 sur toutes les URL une heure apres avoir rendu
#: une page. Sans ce plafond plus bas, chaque lecture ratee ajoutait 45 secondes
#: avant meme d'essayer l'archive.
_TIMEOUT_REPLI = 15.0

#: Meme seuil que la lecture par l'archive, pour la meme raison : sous cette
#: taille, ce n'est pas un article mais un mur de consentement ou une page de
#: redirection, et la rendre ferait chercher au modele un verbatim dans un texte
#: qui n'en porte aucun, ce qui est exactement la situation ou il en invente un.
_TAILLE_MINIMALE = 200


#: Un relais qui rend le corps de la page rend aussi, parfois, le compte rendu
#: d'un echec de l'amont sous un HTTP 200 a lui. Sans cette lecture, un lien mort
#: arrivait au modele comme un article dont le passage cherche « ne figure pas
#: dans la source » : le refus accusait la citation la ou l'adresse etait fausse.
_ERREUR_AMONT = re.compile(r"target url returned error\s*(\d{3})", re.IGNORECASE)

#: Le compte rendu ci-dessus ne couvre que les sites qui repondent un vrai code
#: d'erreur. Beaucoup servent leur page « introuvable » en HTTP 200, et le relais
#: n'a alors rien d'anormal a signaler. Mesure du 2026-08-28 en production :
#: une URL inventee sur lemonde.fr rend 63 456 caracteres de menus, sous le titre
#: « Erreur 404 ». Le titre est ce qui reste pour la reconnaitre.
_TITRE_RELAIS = re.compile(r"^Title:\s*(.+)$", re.MULTILINE)
_TITRE_ERREUR = re.compile(
    r"(erreur|error|http)\s*[:\-]?\s*[45]\d\d\b"
    r"|^\s*[45]\d\d\s*$"
    r"|page (not found|introuvable|non trouv|indisponible)"
    r"|\bnot found\b",
    re.IGNORECASE,
)


def _gabarits() -> list[str]:
    return [g.strip() for g in settings.lecture_relais_endpoint.split(",") if g.strip()]


def _adresse(gabarit: str, url: str) -> str:
    # `str.replace` et non `str.format` : une URL peut porter des accolades, que
    # `format` interpreterait comme des champs et sur lesquelles il leverait.
    return gabarit.replace("{url_encode}", quote(url, safe="")).replace("{url}", url)


def _entetes(*, avec_cle: bool) -> dict[str, str]:
    entetes = {"Accept": "text/plain, text/markdown, */*"}
    cle = settings.lecture_relais_api_key.strip()
    if avec_cle and cle:
        # Sans clé le defaut plafonne autour de 20 requetes par minute, ce qui
        # tient pour un usage humain et casse sur un import de fiche entiere. La
        # clé n'accompagne que le premier gabarit : c'est celui qu'on configure
        # quand on paie un relais, et un secret n'a rien a faire chez les replis
        # anonymes qui suivent.
        entetes["Authorization"] = f"Bearer {cle}"
    return entetes


def _titre_et_texte(corps: str) -> tuple[str | None, str]:
    """Le titre et le texte lisible, que le relais rende du markdown ou du HTML."""
    if not corps.lstrip()[:200].lower().startswith(("<!doctype", "<html", "<?xml")):
        entete = _TITRE_RELAIS.search(corps[:1000])
        return (entete.group(1).strip() if entete else None), corps.strip()
    soup = BeautifulSoup(corps, "lxml")
    balise_titre = soup.find("title")
    titre = balise_titre.get_text(strip=True) if balise_titre else None
    for balise in soup(["script", "style", "noscript", "template"]):
        balise.decompose()
    return (titre or None), soup.get_text(separator=" ", strip=True)


async def _lire(gabarit: str, url: str, *, premier: bool) -> str | None:
    from app.extractors.url_extractor import _looks_like_challenge_page

    adresse = _adresse(gabarit, url)
    delai = _TIMEOUT if premier else _TIMEOUT_REPLI
    try:
        async with httpx.AsyncClient(timeout=delai, follow_redirects=True) as client:
            reponse = await client.get(adresse, headers=_entetes(avec_cle=premier))
    except Exception as e:  # noqa: BLE001 -- une route de repli ne fait jamais echouer l'appelant.
        # Le type autant que le message : un `ReadTimeout` a un message vide, et
        # sans son nom le journal n'apprend rien a qui cherche.
        logger.info("Relais muet pour %s : %s %s", url, type(e).__name__, e)
        return None
    if reponse.status_code != 200:
        logger.info("Relais a repondu %s pour %s", reponse.status_code, url)
        return None
    brut = reponse.text
    amont = _ERREUR_AMONT.search(brut[:2000])
    if amont:
        logger.info("Relais : l'amont a repondu %s pour %s", amont.group(1), url)
        return None
    titre, texte = _titre_et_texte(brut)
    if titre and _TITRE_ERREUR.search(titre):
        logger.info("Relais : page d'erreur intitulee %r pour %s", titre, url)
        return None
    # Le relais peut avoir recu le defi anti-robot plutot que la page. Rendre
    # « Un instant, verification de votre navigateur » comme corps d'article
    # ferait conclure au modele que l'article ne dit rien.
    #
    # Le detecteur est applique sans borne de taille, contrairement a ce qu'on
    # ferait sur une page HTML. Mesure du 2026-08-28 sur ScienceDirect : le
    # relais a rendu le mur Cloudflare d'Elsevier sous **112 998 caracteres**,
    # titre « Just a moment... » et corps rempli de blobs. Une borne de taille
    # aurait laisse passer ce mur pour un article. Le prix est qu'un vrai
    # article contenant « access denied » sera ecarte a tort ; il tombe alors
    # sur le relais suivant puis sur l'archive, et se tromper dans ce sens coute
    # une lecture, tandis que se tromper dans l'autre coute un extrait faux.
    if _looks_like_challenge_page(titre, texte) or len(texte) < _TAILLE_MINIMALE:
        return None
    return texte


async def texte_par_relais(url: str | None) -> str | None:
    """Le texte de la page vu par un relais de la chaine, ou None. Ne leve jamais.

    ``None`` ne dit pas « page introuvable » : il couvre aussi un quota atteint
    et une chaine entierement en panne. C'est pourquoi l'appelant enchaine sur
    l'archive au lieu de conclure quoi que ce soit.
    """
    propre = (url or "").strip()
    if not propre:
        return None
    for rang, gabarit in enumerate(_gabarits()):
        texte = await _lire(gabarit, propre, premier=rang == 0)
        if texte:
            logger.info("Lu par le relais rang=%s url=%s caracteres=%s", rang, propre, len(texte))
            return texte
    return None
