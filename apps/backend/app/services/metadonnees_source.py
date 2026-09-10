"""Le modele choisit quel resolveur fait foi, il ne saisit plus les valeurs.

Un agent qui tape lui-meme le titre et les auteurs d'une source peut les
inventer, et un titre plausible ne se distingue d'un titre vrai qu'en allant
verifier. La reponse n'est pas de le lui interdire, c'est de ne plus le lui
demander : il declare une origine, et l'origine remplit les champs.

Ce que l'origine choisie ne rend pas reste vide. Un champ vide se voit et se
corrige ; un champ rempli au hasard se propage.

Sans etat, volontairement : le resolveur est relance a chaque appel plutot que
mis en cache entre deux tours. Les fonctions de `tools_write` servent a la fois
l'agent et le serveur MCP expose aux clients externes, et ce second chemin n'a
pas de contexte de tour ou un cache pourrait vivre.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.extractors.openalex_metadonnees import chercher_par_doi as openalex_par_doi
from app.extractors.url_extractor import ExtractedMetadata, crossref_lookup, scraper_la_page
from app.models.source import MetadataOrigin

#: Les champs dont l'origine prend la responsabilite. Les autres (`category`,
#: `author_kind`, `format`, `stance`, `annotation`) sont des choix editoriaux du
#: createur, pas des faits sur la source : personne ne peut les resoudre.
CHAMPS_RESOLUS = ("title", "authors", "published_at", "journal", "publisher")


class OrigineIndisponibleError(Exception):
    """L'origine demandee ne peut pas repondre pour cette source.

    Porte un message adresse au modele : ce qui manque, et quoi faire ensuite.
    """


@dataclass(frozen=True)
class Ecart:
    """Une valeur proposee par l'appelant que le resolveur contredit."""

    champ: str
    propose: str
    retenu: str | None


async def resoudre(origine: str, *, url: str | None, doi: str | None) -> ExtractedMetadata | None:
    """Interroge l'origine demandee. `None` pour `createur`, qui ne resout rien.

    Leve `OrigineIndisponibleError` quand l'origine ne peut pas repondre : sans
    DOI pour Crossref ou OpenAlex, ou quand la page refuse la lecture. Le refus
    nomme une porte de sortie, sans quoi le modele boucle sur la meme origine.
    """
    # L'origine se valide avant tout le reste : sinon `resoudre("wikipedia")`
    # tombe dans la branche du DOI et reproche a l'appelant un DOI manquant,
    # ce qui l'envoie chercher un identifiant pour une origine qui n'existe pas.
    if origine not in {o.value for o in MetadataOrigin}:
        connues = ", ".join(o.value for o in MetadataOrigin)
        raise OrigineIndisponibleError(f"metadata_from vaut {origine!r} ; valeurs : {connues}.")

    if origine == MetadataOrigin.CREATEUR.value:
        return None

    if origine == MetadataOrigin.PAGE.value:
        adresse = (url or "").strip()
        if not adresse:
            raise OrigineIndisponibleError(
                "L'origine 'page' demande une url. Donnez-en une, ou choisissez "
                "'crossref' ou 'openalex' si vous avez un doi."
            )
        metadonnees = await scraper_la_page(adresse)
        if metadonnees is not None and metadonnees.access_blocked:
            raise OrigineIndisponibleError(
                "Cette page refuse la lecture automatique : ses metadonnees ne "
                "peuvent pas en etre tirees. Avec un doi, essayez 'crossref' ou "
                "'openalex'. Sinon, le createur dicte ce qu'il a sous les yeux "
                "et vous passez metadata_from='createur'."
            )
        return metadonnees

    identifiant = (doi or "").strip()
    if not identifiant:
        raise OrigineIndisponibleError(
            f"L'origine '{origine}' resout un doi, et cet appel n'en porte pas. "
            "Passez le doi, ou choisissez 'page' pour lire l'adresse."
        )

    if origine == MetadataOrigin.CROSSREF.value:
        return await crossref_lookup(identifiant)
    return await openalex_par_doi(identifiant)


def ecarts(metadonnees: ExtractedMetadata | None, propose: dict[str, str | None]) -> list[Ecart]:
    """Les valeurs proposees que le resolveur contredit.

    Fonction pure. Elles sont rendues dans le resultat de l'outil plutot
    qu'ecartees en silence : un modele qui ne voit pas l'ecart le refera, et un
    createur qui ne le voit pas ne saura pas que sa source porte autre chose que
    ce qu'on lui avait annonce. Un champ que le resolveur n'a pas rempli n'est
    pas un ecart, seulement un vide.
    """
    if metadonnees is None:
        return []
    trouves = []
    for champ, valeur in propose.items():
        attendu = (valeur or "").strip()
        if not attendu or champ not in CHAMPS_RESOLUS:
            continue
        retenu = (getattr(metadonnees, champ, None) or "").strip()
        if retenu and retenu != attendu:
            trouves.append(Ecart(champ=champ, propose=attendu, retenu=retenu))
    return trouves
