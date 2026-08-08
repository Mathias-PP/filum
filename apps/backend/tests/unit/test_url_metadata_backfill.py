"""Backfill des metadonnees par visite de l'URL.

Filet pour les corpus non-academiques (description YouTube, notes de blog) :
ni DOI, ni entree bibliographique redigee, donc ni Crossref ni le LLM
bibliographique ne peuvent produire un titre. Sans ce backfill l'utilisateur
recoit une liste d'URLs nues.
"""

from __future__ import annotations

import pytest

from app.api.v1.endpoints import imports as imports_mod
from app.extractors.url_extractor import ExtractedMetadata
from app.services.import_parsers import ImportedRef


def _fake_extract(mapping: dict[str, ExtractedMetadata]):
    async def _inner(url: str) -> ExtractedMetadata:
        return mapping.get(url, ExtractedMetadata())

    return _inner


@pytest.mark.asyncio
async def test_backfill_fills_title_authors_year(monkeypatch):
    monkeypatch.setattr(
        imports_mod,
        "extract_url_metadata",
        _fake_extract(
            {
                "https://who.int/diabetes": ExtractedMetadata(
                    title="Diabetes",
                    authors="World Health Organization",
                    published_at="2024-11-14",
                    category="rapport",
                )
            }
        ),
    )
    ref = ImportedRef(url="https://who.int/diabetes")
    await imports_mod._backfill_url_metadata([ref])
    assert ref.title == "Diabetes"
    assert ref.authors == "World Health Organization"
    assert ref.year == 2024
    assert ref.category == "rapport"


@pytest.mark.asyncio
async def test_backfill_skips_refs_that_already_have_a_title(monkeypatch):
    called: list[str] = []

    async def _spy(url: str) -> ExtractedMetadata:
        called.append(url)
        return ExtractedMetadata(title="Ecrase")

    monkeypatch.setattr(imports_mod, "extract_url_metadata", _spy)
    ref = ImportedRef(url="https://example.com/a", title="Titre deja connu")
    await imports_mod._backfill_url_metadata([ref])
    assert ref.title == "Titre deja connu"
    assert called == []


@pytest.mark.asyncio
async def test_backfill_skips_dois(monkeypatch):
    # Crossref est autoritatif sur les DOIs et tourne avant : re-visiter
    # l'URL ne ferait que risquer d'ecraser une metadonnee canonique.
    called: list[str] = []

    async def _spy(url: str) -> ExtractedMetadata:
        called.append(url)
        return ExtractedMetadata(title="Depuis la page")

    monkeypatch.setattr(imports_mod, "extract_url_metadata", _spy)
    ref = ImportedRef(url="https://doi.org/10.1234/abc")
    await imports_mod._backfill_url_metadata([ref])
    assert called == []
    assert ref.title is None


@pytest.mark.asyncio
async def test_backfill_ne_laisse_personne_de_cote(monkeypatch):
    """Aucune ref n'est ecartee sur son rang dans la liste.

    Mesure du 2026-08-08 sur gwern.net/scaling-hypothesis : le plafond de 60
    visites ecartait 17 des 77 candidats, dont cinq pages Wikipedia qui
    rendaient leur titre en une requete. Le rang dans la liste n'est pas un
    critere : ces cinq sources arrivaient nues sur la fiche sans que rien ne
    dise qu'on ne leur avait rien demande.
    """
    called: list[str] = []

    async def _spy(url: str) -> ExtractedMetadata:
        called.append(url)
        return ExtractedMetadata(title="T")

    monkeypatch.setattr(imports_mod, "extract_url_metadata", _spy)
    refs = [ImportedRef(url=f"https://example.com/{i}") for i in range(200)]
    await imports_mod._backfill_url_metadata(refs)
    assert len(called) == 200
    assert all(r.title == "T" for r in refs)


@pytest.mark.asyncio
async def test_backfill_rend_la_main_quand_le_budget_est_epuise(monkeypatch):
    """Ce qui est borne est le temps, et ce qui est revenu reste acquis.

    Sans cette borne, une seule page qui ne repond jamais suspendrait
    l'import entier ; avec elle, l'ecran recoit les titres deja obtenus.
    """
    import asyncio

    async def _lent(url: str) -> ExtractedMetadata:
        if url.endswith("/lent"):
            await asyncio.sleep(30)
        return ExtractedMetadata(title="T")

    monkeypatch.setattr(imports_mod, "extract_url_metadata", _lent)
    monkeypatch.setattr(imports_mod, "_URL_BACKFILL_BUDGET_S", 0.2)
    rapide = ImportedRef(url="https://example.com/rapide")
    lent = ImportedRef(url="https://example.com/lent")
    await imports_mod._backfill_url_metadata([rapide, lent])
    assert rapide.title == "T"
    assert lent.title is None


@pytest.mark.asyncio
async def test_backfill_survives_extractor_failure(monkeypatch):
    async def _boom(url: str) -> ExtractedMetadata:
        raise RuntimeError("réseau")

    monkeypatch.setattr(imports_mod, "extract_url_metadata", _boom)
    ref = ImportedRef(url="https://example.com/a")
    await imports_mod._backfill_url_metadata([ref])  # ne doit pas lever
    assert ref.title is None
