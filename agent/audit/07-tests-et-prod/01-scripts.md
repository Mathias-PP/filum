# 07-01 — Scripts (build_workspace_seed, export_openapi)

> **Fiche du lot 7.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G7**.
> **Fichiers :** `apps/backend/app/scripts/build_workspace_seed.py` (72 l., 2 symboles), `apps/backend/app/scripts/export_openapi.py` (43 l., 1 symbole).

## Rôle

Deux scripts utilitaires :
- `build_workspace_seed.py` : copie le workspace de dev (`workspaces/createur-de-fiches/`) vers le seed (`agent_workspace_seed/`), en excluant les fichiers non pertinentes. Purge les anciens fichiers orphelins.
- `export_openapi.py` : exporte le schéma OpenAPI de l'app FastAPI en JSON pour la génération des types TypeScript frontend.

## Symboles

| Symbole | Ligne | Fichier | Rôle |
|---|---|---|---|
| `_included` | `apps/backend/app/scripts/build_workspace_seed.py:35` | build_workspace_seed | Vérifie si un fichier relatif est dans les prefixes inclus |
| `main` | `apps/backend/app/scripts/build_workspace_seed.py:39` | build_workspace_seed | Copie les fichiers et purge les orphelins |
| `main` | `apps/backend/app/scripts/export_openapi.py:23` | export_openapi | Exporte le schéma OpenAPI en JSON |

## Invariants

- `build_workspace_seed.py` (`apps/backend/app/scripts/build_workspace_seed.py:1`) : idempotent — relancer ne casse rien, purge les fichiers renommés.
- `export_openapi.py` (`apps/backend/app/scripts/export_openapi.py:1`) : définit `CI=true` pour éviter les erreurs de secrets manquants.

## Dettes

- `export_openapi.py` : les variables d'env sont en dur dans le script — acceptable car c'est un export readonly.
