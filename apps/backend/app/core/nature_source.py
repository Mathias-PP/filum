"""La nature d'une source quand les faits la disent : DOI, hebergeur, domaine public.

Mesure du 2026-09-14 sur la base de production : 68 sources « page-web /
individu », dont l'OMS, l'Inserm, Pasteur, ameli, sante.fr, la FAO, un site du
gouvernement australien et des universites ; deux videos YouTube en « texte ».
Chaque chemin d'ecriture avait sa valeur par defaut (l'import « page-web /
individu », le MCP « article-scientifique / chercheur ») et aucun ne regardait
l'adresse.

La regle ne remplace que les valeurs qui ne disent rien : « texte » pour le
format, « page-web » pour la categorie, « individu » pour l'auteur. Un choix
informatif du createur (« media », « asso », « documentaire »...) n'est jamais
ecrase. Elle ne s'appuie que sur des indices valables pour tout sujet : un DOI
ou une revue, un hebergeur d'articles ou de videos, un suffixe de domaine public
ou academique, et quelques organismes publics sans suffixe distinctif.
`Source` l'applique a chaque insertion et mise a jour.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

FORMAT_NEUTRE = "texte"
CATEGORIE_NEUTRE = "page-web"
AUTEUR_NEUTRE = "individu"

_HEBERGEURS_VIDEO = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv")

#: Ou vivent les articles evalues par les pairs. Une page servie la est un
#: article, meme quand son DOI n'a pas ete releve.
_HEBERGEURS_ARTICLES = (
    "ncbi.nlm.nih.gov",
    "europepmc.org",
    "doi.org",
    "sciencedirect.com",
    "springer.com",
    "nature.com",
    "wiley.com",
    "tandfonline.com",
    "plos.org",
    "frontiersin.org",
    "mdpi.com",
    "bmj.com",
    "thelancet.com",
    "cell.com",
    "science.org",
    "pnas.org",
    "jamanetwork.com",
    "nejm.org",
    "academic.oup.com",
    "cambridge.org",
    "sagepub.com",
    "jstor.org",
    "cairn.info",
    "persee.fr",
    "openedition.org",
    "hal.science",
    "hal.archives-ouvertes.fr",
)

_HEBERGEURS_PREPRINTS = (
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "ssrn.com",
    "osf.io",
    "researchsquare.com",
    "preprints.org",
)

#: Organismes publics dont le domaine ne porte pas de suffixe public.
_ORGANISMES_PUBLICS = (
    "inserm.fr",
    "cnrs.fr",
    "inrae.fr",
    "ird.fr",
    "cea.fr",
    "ameli.fr",
    "sante.fr",
    "has-sante.fr",
    "santepubliquefrance.fr",
    "service-public.fr",
    "insee.fr",
    "bnf.fr",
    "senat.fr",
    "assemblee-nationale.fr",
    "conseil-constitutionnel.fr",
    "conseil-etat.fr",
    "courdecassation.fr",
    "nhs.uk",
    "un.org",
    "fao.org",
    "unesco.org",
    "oecd.org",
    "worldbank.org",
    "imf.org",
)


@dataclass(frozen=True)
class Nature:
    format: str
    category: str
    author_kind: str


def _hote(url: str | None) -> str:
    try:
        hote = (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""
    return hote.removeprefix("www.")


def _sous(hote: str, domaines: tuple[str, ...]) -> bool:
    return any(hote == d or hote.endswith("." + d) for d in domaines)


def _public(hote: str) -> bool:
    etiquettes = hote.split(".")
    return (
        # gouv.fr, legifrance.gouv.fr, gouv.qc.ca ; gov, nih.gov, padil.gov.au ; gob.mx
        any(e in ("gouv", "gov", "gob") for e in etiquettes[1:] or etiquettes)
        or hote.endswith((".int", ".gc.ca", "europa.eu", ".admin.ch"))
        or hote in ("gouv.fr", "europa.eu", "admin.ch")
        or _sous(hote, _ORGANISMES_PUBLICS)
    )


def _academique(hote: str) -> bool:
    etiquettes = hote.split(".")
    # .edu, .edu.au ; .ac.uk, .ac.jp (jamais « ac » seul en tete de nom)
    return "edu" in etiquettes[1:] or "ac" in etiquettes[1:-1]


def nature_corrigee(
    *,
    url: str | None,
    doi: str | None,
    journal: str | None,
    format: str | None,
    category: str | None,
    author_kind: str | None,
) -> Nature:
    """Le format, la categorie et l'auteur, corriges la ou une valeur neutre contredit les faits."""
    hote = _hote(url)
    fmt = format or FORMAT_NEUTRE
    categorie = category or CATEGORIE_NEUTRE
    auteur = author_kind or AUTEUR_NEUTRE

    if fmt == FORMAT_NEUTRE and _sous(hote, _HEBERGEURS_VIDEO):
        fmt = "video"

    preprint = _sous(hote, _HEBERGEURS_PREPRINTS)
    savant = bool((doi or "").strip() or (journal or "").strip()) or _sous(
        hote, _HEBERGEURS_ARTICLES
    )
    if categorie == CATEGORIE_NEUTRE:
        if preprint:
            categorie = "preprint"
        elif savant:
            categorie = "article-scientifique"

    if auteur == AUTEUR_NEUTRE:
        if preprint or savant:
            auteur = "chercheur"
        elif _public(hote):
            auteur = "institution-publique"
        elif _academique(hote):
            auteur = "ecole"

    return Nature(format=fmt, category=categorie, author_kind=auteur)
