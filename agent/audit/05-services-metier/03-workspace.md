# 05-03 — Workspace (filesystem logique, normalisation, seed)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_workspace.py` (320 l., 16 symboles).
> **SHA256 :** `2aa6731fd250a1021a2fa5492507a80f79b57ad16ade83cc369cd2bab9005a6a`

## Rôle

Filesystem logique en base Postgres : création/lecture/écriture/suppression de fichiers et dossiers, seed du template ICM, normalisation de chemins, lecture de frontmatter YAML. Racines fermées (`ALLOWED_ROOTS`). Chaque fonction est scopée par `creator_id`.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `WorkspaceError` | `apps/backend/app/services/agent_workspace.py:39` | Erreur métier : chemin invalide, racine interdite |
| `WorkspaceNotFoundError` | `apps/backend/app/services/agent_workspace.py:43` | Fichier absent du workspace |
| `normaliser_chemin` | `apps/backend/app/services/agent_workspace.py:47` | Normalise et valide un chemin (relatif, pas de `..`, racines fermées) |
| `calculer_sha256` | `apps/backend/app/services/agent_workspace.py:82` | SHA256 d'un contenu string |
| `_parse_frontmatter` | `apps/backend/app/services/agent_workspace.py:93` | Extrait le frontmatter YAML (jamais d'exception) |
| `_deduire_layer` | `apps/backend/app/services/agent_workspace.py:119` | Layer ICM déduit du chemin (L0-L3, None) |
| `_premier_paragraphe` | `apps/backend/app/services/agent_workspace.py:142` | Premier paragraphe non-titre, tronqué, fallback contract |
| `_meta_yaml` | `apps/backend/app/services/agent_workspace.py:167` | Métadonnées d'un fichier entièrement YAML |
| `extraire_meta` | `apps/backend/app/services/agent_workspace.py:180` | Rend (contract, layer) pour un fichier du workspace |
| `_get` | `apps/backend/app/services/agent_workspace.py:201` | SELECT par creator_id + path |
| `lire` | `apps/backend/app/services/agent_workspace.py:215` | Lecture fichier (normalise le chemin d'abord) |
| `ecrire` | `apps/backend/app/services/agent_workspace.py:220` | Upsert : crée ou remplace, recalcule sha256 |
| `lister` | `apps/backend/app/services/agent_workspace.py:247` | Arborescence (fichiers + dossiers intermédiaires) sous un préfixe |
| `supprimer` | `apps/backend/app/services/agent_workspace.py:279` | Suppression fichier |
| `seed` | `apps/backend/app/services/agent_workspace.py:287` | Insère les fichiers manquants du template ICM (idempotent) |
| `assurer_workspace` | `apps/backend/app/services/agent_workspace.py:314` | Seed au premier accès si le workspace est vide |

## Invariants

- `ALLOWED_ROOTS` (`apps/backend/app/services/agent_workspace.py:29`) : `(shared, stages, _core, runs, setup, agents)` — tuple fermé.
- `ALLOWED_TOP_FILES` (`apps/backend/app/services/agent_workspace.py:30`) : `(AGENTS.md, CONTEXT.md)` — fichiers racine autorisés.
- `SEED_DIR` (`apps/backend/app/services/agent_workspace.py:33`) : snapshot gelé du template ICM.
- `_PATH_MAX = 500` (`apps/backend/app/services/agent_workspace.py:35`) : longueur max d'un chemin.
- `_CONTENT_MAX = 1_000_000` (`apps/backend/app/services/agent_workspace.py:36`) : taille max d'un contenu.
- `_CONTRACT_MAX = 240` (`apps/backend/app/services/agent_workspace.py:88`) : longueur max du contract renvoyé au frontend.
- `_FRONTMATTER_RE` (`apps/backend/app/services/agent_workspace.py:90`) : regex du délimiteur `---`.
- `seed()` (`apps/backend/app/services/agent_workspace.py:287`) : idempotent, ne jamais écraser un fichier modifié.
- `normaliser_chemin()` (`apps/backend/app/services/agent_workspace.py:47`) : refuse chemin absolu, `..` hors racine, caractère nul, racines hors liste.

## Dettes

- `_parse_frontmatter()` (`apps/backend/app/services/agent_workspace.py:93`) : ne lève jamais sur YAML invalide — rend `({}, content)`.
- `_deduire_layer()` (`apps/backend/app/services/agent_workspace.py:119`) : hardcodé L0-L3 — ajouter un layer exige modifier cette fonction.
- `supprimer()` (`apps/backend/app/services/agent_workspace.py:279`) : ne supprime pas les dossiers intermédiaires vides — dossiers orphelins possibles.
- `assurer_workspace()` (`apps/backend/app/services/agent_workspace.py:314`) : seed paresseux au premier accès — pas de migration si le seed change.
