"""Le seed servi aux createurs doit rester le miroir exact du workspace.

Le seed vit sous `app/`, donc `ruff format` le reformate ; la source sous
`workspaces/` n'est pas formatee. Les deux ont diverge silencieusement, et
un `build_workspace_seed` aurait rendu la CI rouge en ecrasant la version
formatee. Ce test rend la divergence visible avant le merge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.scripts.build_workspace_seed import SEED_DIR, WORKSPACE, _included


def _fichiers_attendus() -> list[str]:
    return sorted(
        chemin.relative_to(WORKSPACE).as_posix()
        for chemin in WORKSPACE.rglob("*")
        if chemin.is_file()
        and _included(chemin.relative_to(WORKSPACE).as_posix())
        and chemin.name not in (".gitkeep", "CLAUDE.md")
    )


pytestmark = pytest.mark.skipif(
    not WORKSPACE.is_dir(),
    reason="workspaces/createur-de-fiches absent (checkout partiel)",
)


def test_le_seed_contient_exactement_les_fichiers_du_workspace():
    presents = sorted(
        chemin.relative_to(SEED_DIR).as_posix()
        for chemin in Path(SEED_DIR).rglob("*")
        if chemin.is_file()
    )
    assert presents == _fichiers_attendus()


def test_chaque_fichier_du_seed_est_identique_a_sa_source():
    divergents = [
        rel
        for rel in _fichiers_attendus()
        if (SEED_DIR / rel).read_bytes() != (WORKSPACE / rel).read_bytes()
    ]
    assert not divergents, (
        "Seed desynchronise : "
        + ", ".join(divergents)
        + ". Relancer `uv run python -m app.scripts.build_workspace_seed`."
    )
