"""Garde-fous sur les identifiants de revision Alembic.

La colonne `alembic_version.version_num` est un `varchar(32)`. Un identifiant
plus long passe les tests SQLite en local et casse `alembic upgrade head` sur
PostgreSQL, au moment le plus couteux : le deploiement.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"

#: Taille de `alembic_version.version_num`, fixee par Alembic lui-meme.
LONGUEUR_MAX = 32

_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*[\"'](.+?)[\"']", re.MULTILINE)


def _revisions() -> list[tuple[str, str]]:
    trouvees = []
    for fichier in sorted(VERSIONS.glob("*.py")):
        contenu = fichier.read_text(encoding="utf-8")
        correspondance = _REVISION.search(contenu)
        assert correspondance is not None, f"{fichier.name} ne declare pas de `revision`"
        trouvees.append((fichier.name, correspondance.group(1)))
    return trouvees


def test_identifiants_de_revision_tiennent_dans_la_colonne():
    trop_longs = [
        (nom, revision, len(revision))
        for nom, revision in _revisions()
        if len(revision) > LONGUEUR_MAX
    ]
    assert not trop_longs, (
        f"identifiants de revision au-dela de {LONGUEUR_MAX} caracteres : {trop_longs}"
    )


def test_identifiants_de_revision_uniques():
    revisions = [revision for _, revision in _revisions()]
    doublons = {r for r in revisions if revisions.count(r) > 1}
    assert not doublons, f"identifiants de revision en double : {sorted(doublons)}"
