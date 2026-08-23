"""Un extrait ne s'ecrit pas, il se preleve.

Jusqu'ici, poser un extrait revenait a inscrire en base la chaine que
l'appelant avait tapee. Rien n'obligeait cette chaine a exister dans la source :
une IA qui reformulait, traduisait ou inventait un passage produisait une fiche
indiscernable d'une fiche honnete, et c'est precisement le mode d'echec que
Philum existe pour eliminer. La verification etait disponible (`verify_excerpts`)
mais facultative, donc elle n'etait pas une garantie.

Le remede ne peut pas etre une consigne de prompt : une consigne se contourne
en l'ignorant. Il faut que l'insertion elle-meme soit impossible sans preuve.
D'ou la regle de ce module : le serveur va chercher le texte de la source
lui-meme, y retrouve le passage, et **inscrit les caracteres de la page**, pas
ceux de l'appelant. Ce que l'appelant fournit n'est plus un contenu, c'est une
requete de recherche.

Trois issues, et trois seulement :

- le passage est retrouve : l'extrait est pose, `found`, ancres posees ;
- la page ne rend rien (PDF sans couche texte, mur anti-bot, paywall) : on
  accepte en `unreadable`, parce que refuser accuserait la personne pour une
  defaillance du site ;
- la page est lisible et le passage n'y est pas : on refuse. C'est le seul cas
  ou l'insertion echoue, et c'est celui ou elle produirait une affirmation
  fausse.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.excerpt_anchor import Ancrage, Selecteurs, ancrer, selecteurs_pour

#: Au-dessus de cette ressemblance, l'ecart entre le passage demande et le
#: passage trouve tient a la typographie (apostrophes courbes, ligatures d'un
#: PDF, tiret insecable) et non au sens. On pose alors le texte de la page :
#: c'est lui qui fait foi, et l'extrait devient verbatim par construction.
#: En dessous, c'est une reformulation ou une traduction, et on refuse.
SEUIL_TYPOGRAPHIQUE = 0.95

#: Duree de vie du texte d'une page en memoire. Ajouter dix extraits d'un meme
#: article est le geste normal ; sans ce cache, il coute dix telechargements.
#: Court, parce qu'une page qui change pendant le tour doit pouvoir etre relue.
_TTL_SECONDES = 300

#: Borne du cache. Une page peut peser plusieurs centaines de milliers de
#: caracteres : quelques entrees suffisent, un cache non borne fuit.
_TAILLE_CACHE = 8

_cache: dict[str, tuple[float, str, bool, bool]] = {}


@dataclass(frozen=True)
class Prelevement:
    """Ce qui sera reellement inscrit en base, et sur quelle preuve."""

    #: Les caracteres de la page, jamais ceux de l'appelant.
    texte: str
    #: `found` ou `unreadable`. `missing` n'existe pas ici : un passage absent
    #: d'une page lisible ne devient pas un extrait, il devient une erreur.
    statut: str
    selecteurs: Selecteurs | None


class PassageIntrouvableError(Exception):
    """La page est lisible et ne porte pas ce passage."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def vider_le_cache() -> None:
    """Repart d'une page fraiche. Les tests en dependent."""
    _cache.clear()


async def texte_de_page(url: str | None) -> tuple[str, bool, bool]:
    """Texte de la source, memorise le temps d'un enchainement d'extraits."""
    from app.api.v1.endpoints.excerpts import _texte_de_la_source

    cle = url or ""
    maintenant = time.monotonic()
    en_cache = _cache.get(cle)
    if en_cache is not None and maintenant - en_cache[0] < _TTL_SECONDES:
        return en_cache[1], en_cache[2], en_cache[3]

    texte, refuse, complet = await _texte_de_la_source(url)
    if len(_cache) >= _TAILLE_CACHE:
        _cache.pop(next(iter(_cache)), None)
    _cache[cle] = (maintenant, texte, refuse, complet)
    return texte, refuse, complet


def _ressemblance(page: str, demande: str) -> float:
    return SequenceMatcher(None, " ".join(page.split()), " ".join(demande.split())).ratio()


def _prelever(page_text: str, demande: str, complet: bool) -> Prelevement:
    ancrage: Ancrage | None = ancrer(
        page_text, Selecteurs(quote=demande, prefix="", suffix="", offset=None)
    )
    if ancrage is not None and (
        ancrage.exact or _ressemblance(ancrage.texte, demande) >= SEUIL_TYPOGRAPHIQUE
    ):
        return Prelevement(
            texte=ancrage.texte,
            statut="found",
            selecteurs=selecteurs_pour(page_text, ancrage.start, ancrage.end),
        )

    if not complet:
        # On n'a eu qu'un resume : conclure a l'absence accuserait la citation
        # pour un texte qu'on n'a jamais lu.
        return Prelevement(texte=demande, statut="unreadable", selecteurs=None)

    if ancrage is not None:
        raise PassageIntrouvableError(
            "La source dit quelque chose de proche, mais pas ces mots-la. Un "
            "extrait est un verbatim : recopiez les caracteres de la source, "
            "sans traduire ni reformuler. La traduction et la paraphrase vont "
            f"dans `context`. Ce que la source porte reellement : {ancrage.texte[:300]!r}"
        )
    raise PassageIntrouvableError(
        "Ce passage ne figure pas dans la source. Causes les plus frequentes : "
        "le passage a ete traduit, reformule ou reconstitue de memoire, ou il "
        "vient d'une autre source que celle-ci. Un extrait se copie depuis la "
        "page ; s'il n'y figure pas, il n'a pas a etre pose."
    )


async def prelever_dans_la_source(url: str | None, demande: str) -> Prelevement:
    """Retrouve `demande` dans la source, ou refuse.

    Leve `PassageIntrouvableError` quand la page est lisible et ne porte pas le
    passage : c'est la seule barriere qui rende l'invention impossible plutot
    que deconseillee.
    """
    page_text, _refuse, complet = await texte_de_page(url)
    if not page_text.strip():
        # Le site n'a rien rendu. Refuser ici punirait la personne pour un mur
        # anti-bot ou un PDF sans couche texte : on accepte en le declarant.
        return Prelevement(texte=demande, statut="unreadable", selecteurs=None)
    return _prelever(page_text, demande, complet)
