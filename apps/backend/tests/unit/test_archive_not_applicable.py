"""Une source sans URL n'a pas echoue a etre archivee : il n'y a rien a archiver.

Constate en prod (aout 2026) sur une fiche de 152 sources : 4 references
extraites d'un depot editeur n'avaient ni URL ni DOI -- un manuel DSM-IV-TR,
un chapitre de livre. Elles etaient inscrites `failed`, ce qui affirme qu'on a
essaye et que la page est perdue. C'est faux, et le cout est visible :
l'encart « Archivees » affichait 148/152 a perpetuite et le « tout archive »
ne pouvait plus jamais s'allumer, sur une fiche pourtant complete.

`failed` (essaye, definitivement impossible), `pending` (essaye, pas encore
abouti) et « sans objet » sont trois etats distincts. Les confondre fait
mentir le compteur que la fiche vend.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.source import ArchiveStatus
from app.services import wayback as wb


class _FakeDb:
    def __init__(self) -> None:
        self.writes: list[tuple] = []


class _Recorder(wb.WaybackService):
    def __init__(self) -> None:
        super().__init__(_FakeDb(), None)  # type: ignore[arg-type]
        self.triggered: list[str] = []
        self.written: list[tuple] = []

    async def _mark_attempted(self, source_id) -> None:  # type: ignore[override]
        # Pas de base en test unitaire : la tentative n'a rien a dater.
        return None

    async def _trigger_save(self, url: str) -> None:
        self.triggered.append(url)

    async def _lookup_snapshot(self, url: str) -> tuple[str, str] | None:
        return None

    async def _update_source(self, source_id, status, archive_url, archive_timestamp) -> None:  # type: ignore[override]
        self.written.append((source_id, status, archive_url))


@pytest.fixture
def no_sleep(monkeypatch):
    async def _sleep(d: float) -> None:
        return None

    monkeypatch.setattr(wb.asyncio, "sleep", _sleep)


class TestSansObjet:
    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    def test_une_source_sans_url_est_sans_objet_pas_en_echec(self, no_sleep, blank):
        svc = _Recorder()
        sid = uuid4()

        import asyncio

        asyncio.run(svc.archive_batch([(sid, blank)]))

        assert (sid, ArchiveStatus.NOT_APPLICABLE, None) in svc.written
        assert svc.triggered == []

    def test_les_autres_sources_du_lot_sont_traitees_normalement(self, no_sleep):
        """Une reference sans URL au milieu d'un import ne doit pas empecher
        les 151 autres d'etre archivees."""
        svc = _Recorder()
        vide, plein = uuid4(), uuid4()

        import asyncio

        asyncio.run(svc.archive_batch([(vide, ""), (plein, "https://example.org/a")]))

        assert svc.triggered == ["https://example.org/a"]
        statuses = {sid: st for sid, st, _ in svc.written}
        assert statuses[vide] == ArchiveStatus.NOT_APPLICABLE

    def test_une_url_privee_reste_un_echec(self, no_sleep):
        """« Sans objet » ne doit pas devenir le fourre-tout qui absout les
        vrais echecs : une URL de loopback a bien ete jugee, et rejetee."""
        svc = _Recorder()
        sid = uuid4()

        import asyncio

        asyncio.run(svc.archive_batch([(sid, "http://127.0.0.1:8000/interne")]))

        assert (sid, ArchiveStatus.FAILED, None) in svc.written


class TestLEtatEstServable:
    """Un statut que la base sait ecrire mais que l'API ne sait pas relire est
    une panne, pas une limitation.

    Vecu : `not_applicable` a ete ajoute au modele et ecrit par la migration
    024, mais le schema Pydantic en redeclarait une copie restee a trois
    valeurs. La fiche de 152 sources a repondu 500 des sa premiere lecture --
    la fiche de demo, elle, n'avait aucune source concernee et passait. Les
    deux enums ne doivent pas pouvoir diverger.
    """

    def test_le_schema_accepte_tout_statut_que_le_modele_autorise(self):
        from app.schemas.source import ArchiveStatus as SchemaStatus

        assert {s.value for s in SchemaStatus} == {s.value for s in ArchiveStatus}

    def test_la_reponse_publique_lit_bien_cet_enum(self):
        """Egaliser les valeurs ne suffit pas si `SourceResponse` en referencait
        une troisieme copie."""
        from app.schemas.source import ArchiveStatus as SchemaStatus
        from app.schemas.source import SourceResponse

        assert SourceResponse.model_fields["archive_status"].annotation is SchemaStatus
