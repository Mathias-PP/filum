"""Garde-fous sur les identifiants de revision Alembic.

La colonne `alembic_version.version_num` est un `varchar(32)`. Un identifiant
plus long passe les tests SQLite en local et casse `alembic upgrade head` sur
PostgreSQL, au moment le plus couteux : le deploiement.

Le second garde-fou tient a la facon dont le travail arrive ici : deux branches
partent du meme parent, chacune ajoute sa migration, chacune voit une seule tete
dans sa propre CI, et c'est la fusion des deux qui en cree une seconde.
`alembic upgrade head` refuse alors de choisir et le conteneur redemarre en
boucle. Personne ne le voit avant la production ; ce test le voit a chaque PR.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"

#: Taille de `alembic_version.version_num`, fixee par Alembic lui-meme.
LONGUEUR_MAX = 32

_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*[\"'](.+?)[\"']", re.MULTILINE)
_DOWN_REVISION = re.compile(r"^down_revision(?::[^=]+)?\s*=\s*(.+)$", re.MULTILINE)
_CHAINE = re.compile(r"[\"']([^\"']+)[\"']")


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


def _parents() -> set[str]:
    """Toute revision citee comme `down_revision`, y compris dans un tuple."""
    cites: set[str] = set()
    for fichier in sorted(VERSIONS.glob("*.py")):
        correspondance = _DOWN_REVISION.search(fichier.read_text(encoding="utf-8"))
        if correspondance is not None:
            cites.update(_CHAINE.findall(correspondance.group(1)))
    return cites


def test_une_seule_tete():
    tetes = sorted({revision for _, revision in _revisions()} - _parents())
    assert len(tetes) == 1, (
        f"{len(tetes)} tetes Alembic : {tetes}. `alembic upgrade head` echouera au "
        "demarrage. Ajouter une revision de jonction dont le `down_revision` est "
        "le tuple des tetes."
    )
