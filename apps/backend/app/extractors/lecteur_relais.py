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

Le point d'entree est configurable (``lecture_relais_endpoint``) : la valeur par
defaut marche sans clé ni inscription, ce qui evite qu'une installation neuve
soit muette, et un service a IP residentielles peut la remplacer sans toucher au
code le jour ou une barriere resiste au defaut.

Limite assumee, et elle est de nature differente des precedentes : l'URL demandee
est confiee a un tiers. Les sources d'une fiche Philum sont publiques par
construction, mais l'etage se desactive en vidant ``lecture_relais_endpoint``.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

#: Mesures du 2026-08-28 depuis la VM : 8,7 s et 11,1 s pour deux articles
#: complets. Le relais rend une page qu'il va chercher lui-meme, parfois en
#: rendant le JavaScript : sa latence est celle d'un navigateur, pas d'un GET.
_TIMEOUT = 45.0

#: Meme seuil que la lecture par l'archive, pour la meme raison : sous cette
#: taille, ce n'est pas un article mais un mur de consentement ou une page de
#: redirection, et la rendre ferait chercher au modele un verbatim dans un texte
#: qui n'en porte aucun, ce qui est exactement la situation ou il en invente un.
_TAILLE_MINIMALE = 200


def _entetes() -> dict[str, str]:
    entetes = {"Accept": "text/plain, text/markdown, */*"}
    cle = settings.lecture_relais_api_key.strip()
    if cle:
        # Sans clé le defaut plafonne autour de 20 requetes par minute, ce qui
        # tient pour un usage humain et casse sur un import de fiche entiere.
        entetes["Authorization"] = f"Bearer {cle}"
    return entetes


async def texte_par_relais(url: str | None) -> str | None:
    """Le texte de la page vu par le relais, ou None. Ne leve jamais.

    ``None`` ne dit pas « page introuvable » : il couvre aussi un quota atteint
    et un relais en panne. C'est pourquoi l'appelant enchaine sur l'archive au
    lieu de conclure quoi que ce soit.
    """
    from app.extractors.url_extractor import _looks_like_challenge_page

    propre = (url or "").strip()
    gabarit = settings.lecture_relais_endpoint.strip()
    if not propre or not gabarit:
        return None
    # `str.replace` et non `str.format` : une URL peut porter des accolades, que
    # `format` interpreterait comme des champs et sur lesquelles il leverait.
    adresse = gabarit.replace("{url}", propre)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            reponse = await client.get(adresse, headers=_entetes())
    except Exception as e:  # noqa: BLE001 -- une route de repli ne fait jamais echouer l'appelant.
        # Le type autant que le message : un `ReadTimeout` a un message vide, et
        # sans son nom le journal n'apprend rien a qui cherche.
        logger.info("Relais muet pour %s : %s %s", propre, type(e).__name__, e)
        return None
    if reponse.status_code != 200:
        logger.info("Relais a repondu %s pour %s", reponse.status_code, propre)
        return None
    texte = reponse.text.strip()
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
    # sur l'archive, et se tromper dans ce sens coute une lecture, tandis que
    # se tromper dans l'autre coute un extrait faux.
    if _looks_like_challenge_page(None, texte) or len(texte) < _TAILLE_MINIMALE:
        return None
    logger.info("Lu par le relais url=%s caracteres=%s", propre, len(texte))
    return texte
