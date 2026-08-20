"""Gèle le snapshot du workspace ICM dans `app/agent_workspace_seed/`.

À lancer après toute édition du workspace de développement
(`workspaces/createur-de-fiches/`) pour répercuter le template servi aux
nouveaux créateurs (le seed idempotent de la Phase 2 le copie en base).

N'inclut que la **configuration** : AGENTS.md, CONTEXT.md, `shared/`,
`stages/`, `_core/templates/`, `_core/audit/audit_fiche.py`. Exclut les
placeholder `.gitkeep`, le questionnaire de dev (`setup/`), les runs et
CLAUDE.md.

Usage : `uv run python -m app.scripts.build_workspace_seed`
"""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = BACKEND_ROOT.parent.parent / "workspaces" / "createur-de-fiches"
SEED_DIR = BACKEND_ROOT / "app" / "agent_workspace_seed"

INCLUDED_PREFIXES: tuple[str, ...] = (
    "AGENTS.md",
    "CONTEXT.md",
    "shared/",
    "stages/",
    "_core/templates/",
    "_core/audit/audit_fiche.py",
)
EXCLUDED_NAMES: tuple[str, ...] = (".gitkeep", "CLAUDE.md")


def _included(rel: str) -> bool:
    return any(rel == prefix or rel.startswith(prefix) for prefix in INCLUDED_PREFIXES)


def main() -> None:
    if not WORKSPACE.is_dir():
        raise SystemExit(f"Workspace introuvable : {WORKSPACE}")

    written = 0
    for source in sorted(WORKSPACE.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(WORKSPACE).as_posix()
        if not _included(rel) or source.name in EXCLUDED_NAMES:
            continue
        dest = SEED_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        written += 1
        print(f"  [ok] {rel}")

    print(f"\nSnapshot gelé : {written} fichiers -> {SEED_DIR}")


if __name__ == "__main__":
    main()
