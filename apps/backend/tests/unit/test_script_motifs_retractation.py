"""La passe qui pose les motifs sur le corpus."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.extractors.retraction import RetractionStatus
from app.extractors.retraction_watch import AvisRetractionWatch
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.scripts import motifs_retractation as passe


def _avis(statut: RetractionStatus, motif: str) -> AvisRetractionWatch:
    return AvisRetractionWatch(doi="10.1/x", statut=statut, motif=motif, date_avis=date(2010, 1, 1))


async def _source(db, user, **kwargs) -> Source:
    card = BiblioCard(
        id=uuid4(), user_id=user.id, slug=f"fiche-{uuid4().hex[:8]}", title="Fiche", platform="web"
    )
    db.add(card)
    await db.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        url="https://x",
        position=0,
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
        **kwargs,
    )
    db.add(source)
    await db.commit()
    return source


@pytest.mark.asyncio
async def test_pose_le_motif_de_la_bonne_nature(db_session, test_user, monkeypatch):
    source = await _source(db_session, test_user, doi="10.1/X", retraction_status="retracted")

    async def _index():
        return {
            "10.1/x": [
                _avis(RetractionStatus.CORRECTED, "Erreur de forme"),
                _avis(RetractionStatus.RETRACTED, "Falsification of Data;"),
            ]
        }

    monkeypatch.setattr(passe, "telecharger_dump", _index)
    poses, sous_avis = await passe.poser_les_motifs()

    assert (poses, sous_avis) == (1, 1)
    await db_session.refresh(source)
    assert source.retraction_reason == "Falsification of Data;"


@pytest.mark.asyncio
async def test_source_absente_du_jeu_reste_muette(db_session, test_user, monkeypatch):
    """NULL veut dire « motif inconnu ici », et rien n'a le droit de le combler."""
    source = await _source(db_session, test_user, doi="10.1/inconnu", retraction_status="retracted")

    async def _index():
        return {"10.1/autre": [_avis(RetractionStatus.RETRACTED, "Falsification;")]}

    monkeypatch.setattr(passe, "telecharger_dump", _index)
    assert await passe.poser_les_motifs() == (0, 1)
    await db_session.refresh(source)
    assert source.retraction_reason is None


@pytest.mark.asyncio
async def test_source_sans_avis_n_est_pas_examinee(db_session, test_user, monkeypatch):
    await _source(db_session, test_user, doi="10.1/x", retraction_status="none")

    async def _index():
        return {"10.1/x": [_avis(RetractionStatus.RETRACTED, "Falsification;")]}

    monkeypatch.setattr(passe, "telecharger_dump", _index)
    assert await passe.poser_les_motifs() == (0, 0)


@pytest.mark.asyncio
async def test_jeu_indisponible_ne_touche_a_rien(db_session, test_user, monkeypatch):
    source = await _source(
        db_session,
        test_user,
        doi="10.1/x",
        retraction_status="retracted",
        retraction_reason="Ancien",
    )

    async def _rien():
        return None

    monkeypatch.setattr(passe, "telecharger_dump", _rien)
    assert await passe.poser_les_motifs() == (0, 0)
    await db_session.refresh(source)
    assert source.retraction_reason == "Ancien"


@pytest.mark.asyncio
async def test_seconde_passe_n_ecrit_rien(db_session, test_user, monkeypatch):
    """Rejouable : le compteur distingue « pose » de « deja pose »."""
    await _source(db_session, test_user, doi="10.1/x", retraction_status="retracted")

    async def _index():
        return {"10.1/x": [_avis(RetractionStatus.RETRACTED, "Falsification;")]}

    monkeypatch.setattr(passe, "telecharger_dump", _index)
    assert await passe.poser_les_motifs() == (1, 1)
    assert await passe.poser_les_motifs() == (0, 1)
