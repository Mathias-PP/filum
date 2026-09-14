"""Ce qu'un titre et un auteur de source ont le droit d'etre.

Mesure du 2026-09-14 sur la base de production, 12 sources sur 2 917 :

- « Checking your browser - reCAPTCHA » : le titre de la page anti-bot de PMC,
  inscrit a la place de l'article ;
- « regles-douloureuses » : un segment de l'adresse ameli, pas un titre ;
- « https://www.facebook.com/inserm.fr » comme auteur du dossier Inserm ;
- neuf titres Crossref portant leurs balises (`<i>In Vitro</i>`, `Ca<sup>2+</sup>`).

Chaque chemin d'ecriture avait sa garde, ou n'en avait pas. Ces deux fonctions
sont la regle unique, et `Source` les applique a chaque affectation : aucun
chemin (interface, MCP, agent, import, script) ne peut plus inscrire autre chose.
Une valeur refusee devient vide, parce qu'un champ vide se voit et se corrige,
alors qu'une valeur fausse passe pour vraie.
"""

from __future__ import annotations

import html
import re
from urllib.parse import unquote, urlparse

_BALISE = re.compile(r"<[^>]+>")
_ADRESSE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_SEGMENT = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)+$")

#: Formulations des pages-obstacle (Cloudflare, reCAPTCHA, Akamai, Imperva...)
#: qu'aucun titre de contenu n'emploie. Meme famille que les signatures fortes
#: de `url_extractor`, restreinte a ce qui tient dans un titre.
_OBSTACLE_DANS_LE_TITRE = (
    "checking your browser",
    "checking if the site connection is secure",
    "just a moment...",
    "attention required! | cloudflare",
    "verify you are human",
    "verifying you are human",
    "enable javascript and cookies to continue",
    "ddos protection by",
    "unusual traffic from your computer",
    "vérification de votre navigateur",
    "incapsula incident",
    "pardon our interruption",
    "confirm you are a human",
)

#: Titres de pages d'erreur ou d'obstacle, retenus seulement quand ils sont le
#: titre entier : « reCAPTCHA: Human-Based Character Recognition via Web
#: Security Measures » est un article de Science, « reCAPTCHA » seul n'en est pas un.
_OBSTACLE_TITRE_ENTIER = frozenset(
    {
        "recaptcha",
        "captcha",
        "just a moment",
        "attention required",
        "access denied",
        "accès refusé",
        "forbidden",
        "403 forbidden",
        "404 not found",
        "not found",
        "page not found",
        "page introuvable",
        "erreur 404",
        "error 404",
        "robot check",
        "security check",
        "redirecting",
        "please wait",
        "one more step",
        "client challenge",
        "are you a robot?",
    }
)


#: Balise ouvrante collee a un mot et suivie d'une majuscule : dans
#: « Slices<i>In Vitro</i> », la retirer sans espace collait « SlicesIn ».
_BALISE_COLLEE = re.compile(r"(?<=[^\W\d_])<(?!/)[^>]+>(?=[A-Z])")

#: Lettre isolee que la mise en page a detachee de son trait d'union :
#: « by\n<i>N</i>\n-Ethylmaleimide » devenait « N -Ethylmaleimide ».
_TRAIT_DETACHE = re.compile(r"(?<=\b\w) -(?=\w)")


def _normaliser(texte: str) -> str:
    sans_balises = _BALISE.sub("", _BALISE_COLLEE.sub(" ", texte))
    propre = " ".join(html.unescape(sans_balises).split())
    return _TRAIT_DETACHE.sub("-", propre)


def _segments_d_adresse(url: str | None) -> set[str]:
    if not url:
        return set()
    try:
        chemin = unquote(urlparse(url).path)
    except ValueError:
        return set()
    return {s.lower() for s in chemin.split("/") if s}


def titre_bibliographique(titre: str | None, url: str | None = None) -> str | None:
    """Le titre tel qu'une bibliographie peut l'afficher, ou None s'il n'en est pas un."""
    if titre is None:
        return None
    propre = _normaliser(str(titre))
    if not propre:
        return None
    minuscule = propre.lower()
    if any(signe in minuscule for signe in _OBSTACLE_DANS_LE_TITRE):
        return None
    if minuscule.rstrip(" .!…") in _OBSTACLE_TITRE_ENTIER:
        return None
    if _ADRESSE.fullmatch(propre):
        return None
    # Un segment d'adresse recopie : « regles-douloureuses » pour
    # /themes/regles-douloureuses/. Sans l'adresse, rien ne distingue ce cas
    # d'un titre court a trait d'union : on ne le refuse qu'en la tenant.
    if _SEGMENT.fullmatch(minuscule) and minuscule in _segments_d_adresse(url):
        return None
    return propre


def auteurs_bibliographiques(valeur: str | None) -> str | None:
    """Les auteurs, sans balises ni adresses de profil, ou None s'il ne reste personne."""
    if valeur is None:
        return None
    propre = _normaliser(_ADRESSE.sub(" ", str(valeur)))
    # Les separateurs laisses orphelins par une adresse retiree.
    propre = re.sub(r"\s*([,;])(?:\s*[,;])+", r"\1", propre).strip(" ,;")
    if not propre or propre.startswith("@"):
        return None
    return propre
