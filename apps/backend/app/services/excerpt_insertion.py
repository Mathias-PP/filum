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

**Deux issues, et deux seulement : le passage est retrouve, ou l'insertion
echoue.** Il y en avait trois. La troisieme acceptait l'extrait en `unreadable`
quand la page ne rendait rien, au motif que refuser accuserait la personne pour
une defaillance du site. Cette clemence etait le trou par lequel toute la
garantie s'ecoulait : sur une source injoignable, l'appelant ecrivait ce qu'il
voulait, et le texte inscrit redevenait le sien.

Deux choses ont permis de la fermer. D'abord le diagnostic : le refus suivait la
reputation de notre IP et non l'URL, donc « la page ne rend rien » disait
rarement quelque chose de la page. Ensuite les deux etages qui en decoulent
(``lecteur_relais`` puis ``web_archive``), qui vont chercher la meme page depuis
une autre origine. Ce qui reste illisible apres eux l'est vraiment.

Le cout de l'interdit est reel et il est assume : une source qu'aucun etage ne
rend n'est plus citable **par l'agent**. Elle le reste par le createur, qui
colle le passage dans l'interface : c'est un humain qui engage alors sa parole,
et c'est la difference que Philum a pour objet de tenir.
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
    """Ce qui sera reellement inscrit en base, et sur quelle preuve.

    Il n'y a plus de champ `statut` : un prelevement qui existe a ete retrouve
    dans la page, sans quoi il n'y a pas de prelevement mais une exception. Un
    statut a une seule valeur possible ne renseigne personne et laisse croire
    qu'il en existe d'autres.
    """

    #: Les caracteres de la page, jamais ceux de l'appelant.
    texte: str
    selecteurs: Selecteurs


class PassageIntrouvableError(Exception):
    """La page est lisible et ne porte pas ce passage."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SourceIllisibleError(Exception):
    """Aucun etage n'a rendu le texte : aucune preuve n'est etablissable.

    Distincte de `PassageIntrouvableError` parce que le remede l'est aussi. Un
    passage introuvable se corrige en citant les bons mots ; une source
    illisible ne se corrige pas en reessayant, et le dire evite a l'appelant la
    boucle de relances que produit une erreur qui ne distingue pas les deux.
    """

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
            selecteurs=selecteurs_pour(page_text, ancrage.start, ancrage.end),
        )

    if not complet:
        # On n'a eu qu'un resume. Conclure a l'absence accuserait la citation
        # pour un texte qu'on n'a jamais lu, et l'accepter la poserait sans
        # preuve : reste a le dire, en nommant ce qui a ete lu.
        raise SourceIllisibleError(
            "Seul le resume de cette source a pu etre lu, et le passage n'y "
            "figure pas. Il est peut-etre dans le corps de l'article, mais rien "
            "ici ne permet de l'affirmer, donc l'extrait ne sera pas pose. "
            "Cherchez une adresse qui rende le texte integral, ou laissez le "
            "createur coller le passage lui-meme."
        )

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
    """Retrouve `demande` dans la source, ou leve. Ne rend jamais sans preuve.

    `PassageIntrouvableError` quand la page est lisible et ne porte pas le
    passage, `SourceIllisibleError` quand aucun etage n'a rendu son texte. Ce
    sont les deux seules sorties autres qu'un prelevement, et c'est ce qui rend
    l'invention impossible plutot que deconseillee.
    """
    page_text, _refuse, complet = await texte_de_page(url)
    if not page_text.strip():
        raise SourceIllisibleError(
            "Le texte de cette source n'a pu etre obtenu par aucune voie : ni "
            "l'editeur, ni un depot en acces libre, ni un relais de lecture, ni "
            "l'archive du web. Sans texte, rien ne prouve qu'un passage y "
            "figure, et un extrait non prouve ne sera pas pose. Reessayer la "
            "meme adresse ne changera rien : citez une autre adresse pour le "
            "meme contenu, ou laissez le createur coller le passage lui-meme "
            "depuis l'interface. N'inventez pas d'extrait de memoire."
        )
    return _prelever(page_text, demande, complet)
