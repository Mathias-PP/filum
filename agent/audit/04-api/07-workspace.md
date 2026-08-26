# Workspace ICM — fichiers, arbre, seed (`agent_workspace.py`)

## apps/backend/app/api/v1/endpoints/agent_workspace.py
Lu intégralement : oui (120/120 lignes) · sha256: 4683db257c27 · date: 2026-08-25

Lecture/écriture de fichiers de configuration du workspace ICM hébergé (filesystem logique en base), arborescence, et seed idempotent du template ICM. Toute opération est scopée par le créateur authentifié (`apps/backend/app/api/v1/endpoints/agent_workspace.py:4`).

### Routes (5)

| Méthode | Route | Fonction | Rate-limit | Description |
|---|---|---|---|---|
| `GET` | `/agent/workspace/tree` | `arbre_workspace` | non | Arbre des fichiers (filtrable par `prefix`) |
| `GET` | `/agent/workspace/file` | `lire_fichier` | non | Contenu d'un fichier (param `path`) |
| `PUT` | `/agent/workspace/file` | `ecrire_fichier` | oui | Écrit/crée un fichier |
| `DELETE` | `/agent/workspace/file` | `supprimer_fichier` | oui | Supprime un fichier |
| `POST` | `/agent/workspace/seed` | `re_seed_workspace` | oui | Re-seed le template ICM (idempotent) |

### Symbole

- `_fichier_to_read` — `apps/backend/app/api/v1/endpoints/agent_workspace.py:30` — convertit un objet fichier du service en `WorkspaceFileRead` (path, sha256, content, created_at, updated_at).

### Pièges

- `assurer_workspace` est appelé en préalable de `arbre_workspace` (`apps/backend/app/api/v1/endpoints/agent_workspace.py:46`) : crée le workspace s'il n'existe pas encore (seed au premier accès).
- Les erreurs workspace sont distinguées : `WorkspaceNotFoundError` → 404, `WorkspaceError` → 400 (chemin invalide).
