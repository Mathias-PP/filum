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
from typing import Any
from uuid import UUID

import yaml
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


#: Longueur max de la phrase de contrat renvoyee au frontend. Au-dela on
#: tronque : c'est un descripteur, pas la doc complete.
_CONTRACT_MAX = 240

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extrait le frontmatter YAML d'un fichier Markdown.

    Rend (meta, body). Jamais d'exception : un frontmatter absent, mal
    delimite ou avec un YAML invalide rend ``({}, body_apres_bloc)`` ou
    ``({}, content)`` selon les cas. Un frontmatter invalide est skipe du
    body pour ne pas polluer le fallback ``_premier_paragraphe``.
    """
    if not content.startswith("---\n"):
        return {}, content
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        # Delimiteur d'ouverture sans fermeture : on laisse tout tel quel.
        return {}, content
    body_apres = content[match.end() :]
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        # YAML pourri : on skip quand meme le bloc pour que le fallback
        # premier paragraphe n'attrape pas les `---` en tete de fichier.
        return {}, body_apres
    if not isinstance(meta, dict):
        return {}, body_apres
    return meta, body_apres


def _deduire_layer(path: str) -> str | None:
    """Layer ICM deduit du chemin, quand absent du frontmatter.

    - `AGENTS.md` racine        -> L0 (routing racine)
    - `CONTEXT.md` racine        -> L1 (routing pipeline)
    - `stages/*/CONTEXT.md`      -> L2 (contrat de stage)
    - `shared/`, `_core/`,
      `stages/**/references/`    -> L3 (factory)
    - autre                       -> None
    """
    if path == "AGENTS.md":
        return "L0"
    if path == "CONTEXT.md":
        return "L1"
    if path.startswith("stages/") and path.endswith("/CONTEXT.md") and path.count("/") == 2:
        return "L2"
    if path.startswith(("shared/", "_core/")):
        return "L3"
    if path.startswith("stages/") and "/references/" in path:
        return "L3"
    return None


def _premier_paragraphe(body: str) -> str | None:
    """Premier paragraphe non-titre du body, tronque, comme fallback contract.

    Ignore les lignes vides, les titres Markdown (`#`), les blocs de code
    (\\`\\`\\`), les frontmatter residuels.
    """
    for bloc in re.split(r"\n\s*\n", body.strip()):
        ligne = bloc.strip()
        if not ligne:
            continue
        if ligne.startswith("#") or ligne.startswith("```"):
            # Passer au bloc suivant, mais si c'est un titre, chercher le
            # paragraphe apres.
            continue
        if len(ligne) > _CONTRACT_MAX:
            return ligne[: _CONTRACT_MAX - 1].rstrip() + "…"
        return ligne
    # Aucun paragraphe : essayer le premier titre.
    for ligne in body.splitlines():
        propre = ligne.lstrip("# ").strip()
        if propre:
            return propre[:_CONTRACT_MAX]
    return None


def _meta_yaml(content: str) -> dict[str, Any]:
    """Metadonnees d'un fichier entierement YAML, comme une definition d'agent.

    Sans ce cas, le fallback ``_premier_paragraphe`` afficherait la premiere
    ligne du document (« slug: assistant ») en guise de contrat.
    """
    try:
        charge = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}
    return charge if isinstance(charge, dict) else {}


def extraire_meta(path: str, content: str) -> tuple[str | None, str | None]:
    """Rend (contract, layer) pour un fichier du workspace.

    Priorite : frontmatter YAML explicite > deduction par convention (path,
    premier paragraphe). Ce fallback assure que les workspaces existants
    (crees avant l'ajout du frontmatter au seed) affichent quand meme
    quelque chose d'utile dans l'UI, sans migration destructrice.
    """
    if path.endswith((".yaml", ".yml")):
        meta, body = _meta_yaml(content), ""
    else:
        meta, body = _parse_frontmatter(content)
    contract_yaml = meta.get("contract") if isinstance(meta.get("contract"), str) else None
    layer_yaml = meta.get("layer") if isinstance(meta.get("layer"), str) else None
    contract = contract_yaml or _premier_paragraphe(body)
    if contract and len(contract) > _CONTRACT_MAX:
        contract = contract[: _CONTRACT_MAX - 1].rstrip() + "…"
    layer = layer_yaml or _deduire_layer(path)
    return contract, layer


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
        contract, layer = extraire_meta(f.path, f.content)
        entries[f.path] = {
            "path": f.path,
            "type": "file",
            "sha256": f.sha256,
            "updated_at": f.updated_at,
            "contract": contract,
            "layer": layer,
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


def fichiers_du_modele() -> dict[str, str]:
    """Le template ICM tel qu'il est embarqué, chemin relatif → contenu."""
    return {
        f.relative_to(SEED_DIR).as_posix(): f.read_text(encoding="utf-8")
        for f in sorted(SEED_DIR.rglob("*"))
        if f.is_file()
    }


async def seed(db: AsyncSession, creator_id: UUID) -> int:
    """Insère les fichiers manquants du template ICM. Idempotent.

    Ne **jamais** écraser un fichier que l'utilisateur (ou l'agent) a modifié :
    on n'insère que les chemins absents. Pour propager les évolutions du
    template sur un workspace déjà peuplé, voir `resynchroniser()`.
    """
    count = 0
    for rel, content in fichiers_du_modele().items():
        if await _get(db, creator_id, rel) is not None:
            continue
        sha = calculer_sha256(content)
        db.add(
            WorkspaceFile(
                creator_id=creator_id,
                path=rel,
                content=content,
                sha256=sha,
                seed_sha256=sha,
            )
        )
        count += 1
    await db.flush()
    return count


#: Les quatre états possibles d'un fichier du template dans un workspace.
#:
#: `absent`   le template le connaît, le workspace ne l'a pas.
#: `a_jour`   contenus identiques, rien à faire.
#: `obsolete` le contenu diffère du template, mais il est resté exactement ce
#:            que le seed avait posé : personne ne l'a touché ici, donc le
#:            mettre à jour ne fait perdre aucun travail.
#: `diverge`  le contenu diffère du template et ne correspond plus à sa
#:            provenance, ou sa provenance est inconnue (fichier seedé avant
#:            la migration 056). Il a pu être édité : on ne l'écrase jamais
#:            d'office, on le signale.
ETATS = ("absent", "a_jour", "obsolete", "diverge")


async def etat_synchronisation(db: AsyncSession, creator_id: UUID) -> list[dict[str, str]]:
    """Compare le workspace au template, sans rien modifier.

    Ne parle que des chemins du template : un fichier écrit par la personne et
    inconnu du template n'est pas un écart, c'est son travail.
    """
    stmt = select(WorkspaceFile).where(WorkspaceFile.creator_id == creator_id)
    par_chemin = {f.path: f for f in (await db.execute(stmt)).scalars().all()}

    rapport: list[dict[str, str]] = []
    for chemin, attendu in fichiers_du_modele().items():
        fichier = par_chemin.get(chemin)
        if fichier is None:
            etat = "absent"
        elif fichier.content == attendu:
            etat = "a_jour"
        elif fichier.seed_sha256 is not None and fichier.seed_sha256 == fichier.sha256:
            etat = "obsolete"
        else:
            etat = "diverge"
        rapport.append({"path": chemin, "etat": etat})
    return rapport


async def resynchroniser(
    db: AsyncSession,
    creator_id: UUID,
    adopter: list[str] | None = None,
) -> dict[str, object]:
    """Propage les évolutions du template, sans jamais écraser une édition.

    Insère les fichiers `absent`, met à jour les `obsolete`, et laisse les
    `diverge` intacts en les rendant dans le rapport. Un chemin passé dans
    `adopter` est repris du template même s'il diverge : c'est le seul moyen de
    reprendre la version courante en connaissance de cause, et il faut le
    demander explicitement, chemin par chemin.
    """
    demandes = set(adopter or [])
    inconnus = demandes - set(fichiers_du_modele())
    if inconnus:
        raise WorkspaceError(f"Chemins hors du template : {', '.join(sorted(inconnus))}.")

    etats = {ligne["path"]: ligne["etat"] for ligne in await etat_synchronisation(db, creator_id)}
    modele = fichiers_du_modele()
    ajoutes: list[str] = []
    mis_a_jour: list[str] = []
    adoptes: list[str] = []
    divergents: list[str] = []

    for chemin, etat in etats.items():
        if etat == "a_jour":
            continue
        if etat == "diverge" and chemin not in demandes:
            divergents.append(chemin)
            continue
        contenu = modele[chemin]
        sha = calculer_sha256(contenu)
        fichier = await _get(db, creator_id, chemin)
        if fichier is None:
            db.add(
                WorkspaceFile(
                    creator_id=creator_id,
                    path=chemin,
                    content=contenu,
                    sha256=sha,
                    seed_sha256=sha,
                )
            )
            ajoutes.append(chemin)
        else:
            fichier.content = contenu
            fichier.sha256 = sha
            fichier.seed_sha256 = sha
            (adoptes if etat == "diverge" else mis_a_jour).append(chemin)

    await db.flush()
    return {
        "ajoutes": sorted(ajoutes),
        "mis_a_jour": sorted(mis_a_jour),
        "adoptes": sorted(adoptes),
        "divergents": sorted(divergents),
    }


async def assurer_workspace(db: AsyncSession, creator_id: UUID) -> None:
    """Seed au premier accès si le workspace est vide (provisionnement paresseux)."""
    result = await db.execute(
        select(WorkspaceFile.id).where(WorkspaceFile.creator_id == creator_id).limit(1)
    )
    if result.scalar_one_or_none() is None:
        await seed(db, creator_id)
