"""Reapplique aux sources deja en base les regles de nommage et de nature.

    uv run python -m app.scripts.assainir_sources                       # liste, n'ecrit rien
    uv run python -m app.scripts.assainir_sources --ecrire              # corrige
    uv run python -m app.scripts.assainir_sources --ecrire --resoudre   # et relit l'origine

`Source` applique deux regles a l'ecriture :

- `core/champs_bibliographiques.py` a chaque affectation du titre et des auteurs
  (plus de page anti-bot, de segment d'adresse ni de profil en guise d'auteur) ;
- `core/nature_source.py` a chaque enregistrement (plus de « page-web /
  individu » pour l'OMS, plus de video YouTube en « texte »).

Les lignes posees avant elles gardent leur valeur tant qu'on ne les reecrit pas.
Cette passe les reecrit.

Un titre refuse devient vide. Avec `--resoudre`, la source est d'abord relue a son
origine (Crossref quand elle a un DOI, la page sinon, par la meme lecture que
l'import : page directe, relais, archive), et une source PubMed ou PMC sans DOI
recoit celui que NCBI lui associe. Rejouable sans dommage.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.champs_bibliographiques import auteurs_bibliographiques, titre_bibliographique
from app.core.nature_source import nature_corrigee
from app.db.database import async_session_maker
from app.extractors.url_extractor import resolve_doi_from_pubmed
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.services import metadonnees_source

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("assainir")

_CHAMPS = ("title", "authors", "doi", "format", "category", "author_kind")


@dataclass(frozen=True)
class Correction:
    fiche: str
    source_id: str
    avant: dict[str, str | None]
    apres: dict[str, str | None]

    def ecarts(self) -> dict[str, tuple[str | None, str | None]]:
        return {
            c: (self.avant[c], self.apres[c]) for c in _CHAMPS if self.avant[c] != self.apres[c]
        }


async def _relire(source: Source) -> tuple[str | None, str | None]:
    """Le titre et les auteurs que l'origine de la source rend, passes a la regle."""
    origine = "crossref" if source.doi else "page"
    try:
        meta = await metadonnees_source.resoudre(origine, url=source.url, doi=source.doi)
    except metadonnees_source.OrigineIndisponibleError:
        return None, None
    if meta is None:
        return None, None
    return (
        titre_bibliographique(meta.title, source.url),
        auteurs_bibliographiques(meta.authors),
    )


async def _voulu(source: Source, *, resoudre: bool) -> dict[str, str | None]:
    """Les valeurs que les regles donnent a la source, relecture comprise si demandee."""
    titre = titre_bibliographique(source.title, source.url)
    auteurs = auteurs_bibliographiques(source.authors)
    doi = source.doi or None
    if resoudre:
        if doi is None and source.url:
            doi = await resolve_doi_from_pubmed(source.url)
        if titre is None and source.title or auteurs is None and source.authors:
            relu_titre, relus_auteurs = await _relire(source)
            titre = titre or relu_titre
            auteurs = auteurs or relus_auteurs
    nature = nature_corrigee(
        url=source.url,
        doi=doi,
        journal=source.journal,
        format=source.format,
        category=source.category,
        author_kind=source.author_kind,
    )
    return {
        "title": titre,
        "authors": auteurs,
        "doi": doi,
        "format": nature.format,
        "category": nature.category,
        "author_kind": nature.author_kind,
    }


async def assainir(db: AsyncSession, *, ecrire: bool, resoudre: bool) -> list[Correction]:
    lignes = (
        await db.execute(
            select(Source, BiblioCard.slug)
            .join(BiblioCard, BiblioCard.id == Source.biblio_card_id)
            .where(Source.deleted_at.is_(None))
            .order_by(BiblioCard.slug, Source.position)
        )
    ).all()
    corrections: list[Correction] = []
    for source, slug in lignes:
        avant = {champ: getattr(source, champ) for champ in _CHAMPS}
        apres = await _voulu(source, resoudre=resoudre)
        if apres == avant:
            continue
        corrections.append(Correction(slug, str(source.id), avant, apres))
        if ecrire:
            for champ, valeur in apres.items():
                setattr(source, champ, valeur)
    if ecrire:
        await db.commit()
    return corrections


async def dater(db: AsyncSession, *, ecrire: bool, lire_pages: bool) -> list[tuple[str, str, str]]:
    """Les sources sans date qui en recoivent une : (fiche, source, date).

    Par la notice Crossref de leur DOI, pris dans le champ ou dans l'adresse ;
    avec `lire_pages`, les sources sans DOI par leur page (meme lecture que
    l'import, sans modele de langage). Rejouable sans dommage : seules les
    sources encore sans date sont relues.
    """
    from app.extractors.lecture_page import metadonnees_de_la_page
    from app.extractors.url_extractor import crossref_lookup
    from app.mcp_server.tools_write import _valeur_date
    from app.services.content_identity import extract_doi

    lignes = (
        await db.execute(
            select(Source, BiblioCard.slug)
            .join(BiblioCard, BiblioCard.id == Source.biblio_card_id)
            .where(Source.deleted_at.is_(None), Source.published_at.is_(None))
            .order_by(BiblioCard.slug, Source.position)
        )
    ).all()
    datees: list[tuple[str, str, str]] = []
    for source, slug in lignes:
        doi = source.doi or extract_doi(source.url)
        date: str | None = None
        if doi:
            notice = await crossref_lookup(doi)
            date = notice.published_at if notice is not None else None
        elif lire_pages and source.url:
            meta = await metadonnees_de_la_page(source.url, avec_modele=False)
            if meta is not None and not meta.access_blocked:
                date = meta.published_at
        if not date:
            continue
        datees.append((slug, str(source.id), date))
        if ecrire:
            source.published_at = _valeur_date(date)
            source.doi = source.doi or doi
    if ecrire:
        await db.commit()
    return datees


async def _main(ecrire: bool, resoudre: bool) -> None:
    async with async_session_maker() as db:
        corrections = await assainir(db, ecrire=ecrire, resoudre=resoudre)
    for c in corrections:
        details = " | ".join(f"{champ} {a!r} -> {b!r}" for champ, (a, b) in c.ecarts().items())
        logger.info("%s | %s | %s", c.fiche, c.source_id, details)
    verbe = "corrigees" if ecrire else "a corriger (relancer avec --ecrire)"
    logger.info("%s sources %s", len(corrections), verbe)


async def _main_dates(ecrire: bool, lire_pages: bool) -> None:
    async with async_session_maker() as db:
        datees = await dater(db, ecrire=ecrire, lire_pages=lire_pages)
    for fiche, source_id, date in datees:
        logger.info("%s | %s | published_at -> %s", fiche, source_id, date)
    verbe = "datees" if ecrire else "a dater (relancer avec --ecrire)"
    logger.info("%s sources %s", len(datees), verbe)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecrire", action="store_true", help="ecrire les corrections")
    parser.add_argument(
        "--resoudre",
        action="store_true",
        help="relire l'origine pour retrouver un titre refuse, et le DOI des sources PubMed",
    )
    parser.add_argument(
        "--dates",
        action="store_true",
        help="dater les sources sans date par leur DOI (Crossref), au lieu de l'assainissement",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="avec --dates, lire aussi la page des sources sans DOI",
    )
    arguments = parser.parse_args()
    if arguments.dates:
        asyncio.run(_main_dates(arguments.ecrire, arguments.pages))
    else:
        asyncio.run(_main(arguments.ecrire, arguments.resoudre))
