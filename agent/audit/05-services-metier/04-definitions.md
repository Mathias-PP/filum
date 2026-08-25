# 05-04 — Définitions (agents nommés, validation, YAML)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_definitions.py` (192 l., 10 symboles).

## Rôle

Chargement et validation des agents nommés depuis des fichiers YAML du workspace. Tri par nature (builtin vs user-defined), validation des champs requis, gestion des outils absents.

## Architecture

- `AgentDefinition` : modèle Pydantic d'un agent nommé (id, nom, description, system_prompt, tools, metadata).
- `_REQUIRED_FIELDS` : champs requis pour un agent valide (id, nom, system_prompt).
- `_BUILTIN_NATURES` : natures builtin (ne peuvent pas être supprimées).
- `tools_absents` : vérifie que les outils référencés existent dans le registry MCP.

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `AgentDefinitionError` | 12 | Exception métier |
| `AgentDefinition` | 18 | Modèle Pydantic |
| `_REQUIRED_FIELDS` | 38 | Champs requis |
| `_BUILTIN_NATURES` | 41 | Natures builtin |
| `valider_definition` | 46 | Validation complète |
| `tools_absents` | 72 | Vérifie outils MCP |
| `lister_definitions` | 88 | Listage par workspace |
| `lire_definition` | 112 | Lecture fichier YAML |
| `sauvegarder_definition` | 132 | Écriture fichier YAML |
| `supprimer_definition` | 160 | Suppression fichier YAML |
| `trier_par_nature` | 178 | Tri builtin/user |

## Flux typique (lecture)

1. `lire_definition` → lit le fichier YAML du workspace → parse → valide avec `valider_definition`.
2. `valider_definition` → vérifie `_REQUIRED_FIELDS` → vérifie `tools_absents` → retourne `AgentDefinition`.
3. `lister_definitions` → list tous les fichiers YAML du dossier `agents/` → trie avec `trier_par_nature`.

## Dettes et pièges

- `_BUILTIN_NATURES` (`apps/backend/app/services/agent_definitions.py:41`) : ne peut pas être modifié sans changement de code — les agents builtin ne sont pas supprimables.
- `tools_absents` (`apps/backend/app/services/agent_definitions.py:72`) : vérifie l'existence des outils dans le registry MCP au moment de la validation — si un outil est ajouté au YAML mais pas enregistré, la validation échoue.
- `valider_definition` (`apps/backend/app/services/agent_definitions.py:46`) : ne lève pas sur tools absents — retourne une liste vide si tous les outils existent.
- Les agents nommés sont stockés en YAML dans le workspace, pas en base — si le workspace est réinitialisé, les agents sont perdus.
