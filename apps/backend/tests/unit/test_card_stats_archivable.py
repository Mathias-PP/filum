"""Le compteur « Archivees » ne doit pas reprocher a une fiche ce qu'elle
n'a pas a faire.

Une reference sans URL (manuel, chapitre de livre) n'a rien a archiver. Tant
qu'elle comptait au denominateur, une fiche integralement archivee affichait
« 148/152 » et le « tout archive » restait eteint pour toujours.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.models.source import ArchiveStatus
from app.services.card import CardService


def _source(status: str):
    return SimpleNamespace(archive_status=status, author_kind="chercheur")


def _stats(*statuses: str):
    card = SimpleNamespace(sources=[_source(s) for s in statuses])
    return CardService.compute_stats(None, card)  # type: ignore[arg-type]


class TestDenominateur:
    def test_une_source_sans_objet_sort_du_denominateur(self):
        stats = _stats(
            ArchiveStatus.ARCHIVED.value,
            ArchiveStatus.ARCHIVED.value,
            ArchiveStatus.NOT_APPLICABLE.value,
        )
        assert stats.archived_count == 2
        assert stats.archivable_count == 2
        assert stats.all_archived is True

    def test_elle_reste_comptee_dans_le_total_des_sources(self):
        """La reference existe et compte comme source ; c'est seulement
        l'archivage qui ne la concerne pas."""
        stats = _stats(ArchiveStatus.ARCHIVED.value, ArchiveStatus.NOT_APPLICABLE.value)
        assert stats.total_sources == 2

    def test_une_source_en_attente_bloque_toujours_le_tout_archive(self):
        """« Sans objet » ne doit pas devenir une facon de declarer complet ce
        qui ne l'est pas."""
        stats = _stats(
            ArchiveStatus.ARCHIVED.value,
            ArchiveStatus.PENDING.value,
            ArchiveStatus.NOT_APPLICABLE.value,
        )
        assert stats.all_archived is False

    def test_un_echec_bloque_toujours_le_tout_archive(self):
        stats = _stats(ArchiveStatus.ARCHIVED.value, ArchiveStatus.FAILED.value)
        assert stats.all_archived is False

    def test_une_fiche_sans_rien_a_archiver_n_est_pas_declaree_complete(self):
        """Zero sur zero n'est pas un succes : afficher un « tout archive »
        sur une fiche ou rien n'a ete archive serait vide de sens."""
        stats = _stats(ArchiveStatus.NOT_APPLICABLE.value)
        assert stats.all_archived is False

    def test_une_fiche_vide_n_est_pas_declaree_complete(self):
        stats = _stats()
        assert stats.all_archived is False
