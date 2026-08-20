"""Workspace de configuration ICM hébergé d'un créateur.

Chaque créateur a une copie persistée en base du template ICM (see
`app/agent_workspace_seed/`) : AGENTS.md, CONTEXT.md, `shared/`, `stages/`,
`_core/`. Il s'agit d'un filesystem logique — pas de disque — dont les chemins
sont strictement normalisés : relatifs, sans remontée hors racine, racines
fermées. Le `sha256` de chaque fichier traçe son contenu pour l'audit de
l'agent.

Toute fonction est scopée par `creator_id` : un créateur ne voit jamais le
workspace d'un autre.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto.hashing import HashService
from app.models.workspace_file import WorkspaceFile

#: Racines autorisées (premier segment d'un chemin) + fichiers racine.
ALLOWED_ROOTS: tuple[str, ...] = ("shared", "stages", "_core", "runs", "setup", "agents")
ALLOWED_TOP_FILES: tuple[str, ...] = ("AGENTS.md", "CONTEXT.md")

#: Répertoire du snapshot gelé du template ICM, embarqué dans le package.
SEED_DIR = Path(__file__).resolve().parent.parent / "agent_workspace_seed"

_PATH_MAX = 500
_CONTENT_MAX = 1_000_000


class WorkspaceError(ValueError):
    """Erreur métier : chemin invalide, racine interdite, ressource d'autrui."""


class WorkspaceNotFoundError(WorkspaceError):
    """Le fichier n'existe pas dans le workspace de ce créateur."""


def normaliser_chemin(path: str) -> str:
    """Normalise et valide un chemin de workspace.

    Refuse : chemin vide, absolu (`/...`, `C:\\...`), URL, remontees `..` hors
    racine, caractere nul, racines hors liste fermee. Les backslashes sont
    acceptes (le monde Windows) et convertis en `/`.
    """
    if not isinstance(path, str) or not path.strip():
        raise WorkspaceError("Chemin vide.")
    p = path.replace("\\", "/").strip()
    if p.startswith("/") or re.match(r"^[a-zA-Z]:", p) or "://" in p:
        raise WorkspaceError("Chemin absolu interdit.")
    parts = [part for part in p.split("/") if part not in ("", ".")]
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if not resolved:
                raise WorkspaceError("Chemin hors du workspace.")
            resolved.pop()
        else:
            if "\x00" in part:
                raise WorkspaceError("Caractère nul interdit.")
            resolved.append(part)
    if not resolved:
        raise WorkspaceError("Chemin vide.")
    normalized = "/".join(resolved)
    if len(normalized) > _PATH_MAX:
        raise WorkspaceError("Chemin trop long.")
    if normalized in ALLOWED_TOP_FILES:
        return normalized
    if resolved[0] not in ALLOWED_ROOTS:
        raise WorkspaceError(f"Racine interdite : {resolved[0]!r}.")
    return normalized


def calculer_sha256(content: str) -> str:
    return HashService.sha256(content.encode("utf-8"))


async def _get(
    db: AsyncSession,
    creator_id: UUID,
    path: str,
) -> WorkspaceFile | None:
    result = await db.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.creator_id == creator_id,
            WorkspaceFile.path == path,
        )
    )
    return result.scalar_one_or_none()


async def lire(db: AsyncSession, creator_id: UUID, path: str) -> WorkspaceFile | None:
    normalized = normaliser_chemin(path)
    return await _get(db, creator_id, normalized)


async def ecrire(
    db: AsyncSession,
    creator_id: UUID,
    path: str,
    content: str,
) -> WorkspaceFile:
    """Upsert : écrit le fichier (crée ou remplace) et recalcule son sha256."""
    if len(content) > _CONTENT_MAX:
        raise WorkspaceError("Contenu trop volumineux.")
    normalized = normaliser_chemin(path)
    sha = calculer_sha256(content)
    existing = await _get(db, creator_id, normalized)
    if existing is not None:
        existing.content = content
        existing.sha256 = sha
        return existing
    fichier = WorkspaceFile(
        creator_id=creator_id,
        path=normalized,
        content=content,
        sha256=sha,
    )
    db.add(fichier)
    await db.flush()
    return fichier


async def lister(
    db: AsyncSession,
    creator_id: UUID,
    prefix: str | None = None,
) -> list[dict[str, object]]:
    """Arborescence (fichiers + dossiers intermédiaires) sous un préfixe."""
    stmt = select(WorkspaceFile).where(WorkspaceFile.creator_id == creator_id)
    if prefix:
        stmt = stmt.where(WorkspaceFile.path.startswith(normaliser_chemin(prefix)))
    stmt = stmt.order_by(WorkspaceFile.path)
    result = await db.execute(stmt)
    fichiers = result.scalars().all()

    entries: dict[str, dict[str, object]] = {}
    for f in fichiers:
        entries[f.path] = {
            "path": f.path,
            "type": "file",
            "sha256": f.sha256,
            "updated_at": f.updated_at,
        }
        parts = f.path.split("/")
        for i in range(1, len(parts)):
            dossier = "/".join(parts[:i])
            if dossier and dossier not in entries:
                entries[dossier] = {"path": dossier, "type": "directory"}
    return sorted(entries.values(), key=lambda e: str(e["path"]))


async def supprimer(db: AsyncSession, creator_id: UUID, path: str) -> None:
    normalized = normaliser_chemin(path)
    fichier = await _get(db, creator_id, normalized)
    if fichier is None:
        raise WorkspaceNotFoundError("Fichier introuvable.")
    await db.delete(fichier)


async def seed(db: AsyncSession, creator_id: UUID) -> int:
    """Insère les fichiers manquants du template ICM. Idempotent.

    Ne **jamais** écraser un fichier que l'utilisateur (ou l'agent) a modifié :
    on n'insère que les chemins absents.
    """
    count = 0
    for fichier_disk in sorted(SEED_DIR.rglob("*")):
        if not fichier_disk.is_file():
            continue
        rel = fichier_disk.relative_to(SEED_DIR).as_posix()
        if await _get(db, creator_id, rel) is not None:
            continue
        content = fichier_disk.read_text(encoding="utf-8")
        db.add(
            WorkspaceFile(
                creator_id=creator_id,
                path=rel,
                content=content,
                sha256=calculer_sha256(content),
            )
        )
        count += 1
    await db.flush()
    return count


async def assurer_workspace(db: AsyncSession, creator_id: UUID) -> None:
    """Seed au premier accès si le workspace est vide (provisionnement paresseux)."""
    result = await db.execute(
        select(WorkspaceFile.id).where(WorkspaceFile.creator_id == creator_id).limit(1)
    )
    if result.scalar_one_or_none() is None:
        await seed(db, creator_id)
