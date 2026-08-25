# 05-03 — Workspace (filesystem logique, normalisation, seed)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_workspace.py` (320 l., 16 symboles).

## Rôle

Filesystem logique en base Postgres : création/lecture/écriture/suppression de fichiers et dossiers, seed du template ICM, normalisation de chemins, lecture de frontmatter YAML. Racines fermées (ALLOWED_ROOTS).

## Architecture

- `ALLOWED_ROOTS` : tuple fermé des racines autorisées (shared, stages, _core, runs, setup, agents).
- `ALLOWED_TOP_FILES` : tuple des fichiers autorisés à la racine (AGENTS.md, CONTEXT.md).
- `_PATH_MAX` : 500 caractères max par chemin.
- `_CONTENT_MAX` : 1 000 000 caractères max par contenu.
- `_RESERVED_NAMES` : noms réservés (CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9, ...).

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `ALLOWED_ROOTS` | 29 | Racines fermées |
| `ALLOWED_TOP_FILES` | 31 | Fichiers racine autorisés |
| `_PATH_MAX` | 33 | 500 chars max |
| `_CONTENT_MAX` | 34 | 1M chars max |
| `_RESERVED_NAMES` | 36 | Noms réservés Windows |
| `WorkspaceError` | 43 | Exception métier |
| `normaliser_chemin` | 49 | Normalisation path |
| `_valider_racine` | 82 | Validation racine |
| `_parse_frontmatter` | 93 | Parsing YAML frontmatter |
| `lire_fichier` | 118 | Lecture fichier |
| `lire_dossier` | 134 | Lecture dossier |
| `ecrire_fichier` | 148 | Écriture fichier |
| `creer_dossier` | 176 | Création dossier |
| `supprimer` | 192 | Suppression fich/dossier |
| `deplacer` | 212 | Déplacement fich/dossier |
| `copier` | 238 | Copie fichier |
| `rechercher` | 262 | Recherche texte |
| `seed` | 287 | Seed template ICM |

## Flux typique (seed)

1. `seed()` (`apps/backend/app/services/agent_workspace.py:287`) : lit le template ICM (`template_icm/`), crée les dossiers et fichiers absents dans le workspace.
2. Idempotent : ne jamais écraser un fichier modifié — ne fait qu'insérer les chemins absents.
3. `_parse_frontmatter` (`apps/backend/app/services/agent_workspace.py:93`) : les YAML pourris et les délimiteurs ouverts sans fermeture rendent `({}, content)` sans exception.

## Dettes et pièges

- `ALLOWED_ROOTS` (`apps/backend/app/services/agent_workspace.py:29`) : tuple fermé — toute ajout de racine est un changement de sécurité, exige revue.
- `ALLOWED_TOP_FILES` (`apps/backend/app/services/agent_workspace.py:31`) : tuple fermé — tout ajout de fichier racine est un changement de sécurité.
- `_RESERVED_NAMES` (`apps/backend/app/services/agent_workspace.py:36`) : noms réservés Windows — ne pas retirer même si le backend tourne sur Linux (portabilité).
- `_parse_frontmatter` (`apps/backend/app/services/agent_workspace.py:93`) : ne lève jamais sur YAML invalide — rend `({}, content)`.
- `seed()` (`apps/backend/app/services/agent_workspace.py:287`) : idempotent, ne jamais écraser un fichier modifié.
- `_PATH_MAX=500` (`apps/backend/app/services/agent_workspace.py:33`) : pourrait être un problème pour les chemins profonds du template ICM.
