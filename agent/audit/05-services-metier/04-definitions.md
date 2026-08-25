# 05-04 — Définitions (agents nommés, validation, YAML)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_definitions.py` (192 l., 10 symboles).
> sha256: d46d5c009b4711b0053a1a3158a617ff0ef67f818aae4464cc55ccaa1ce725df

## Rôle

Chargement et validation des agents nommés depuis des fichiers YAML du workspace. Tri par nature (builtin vs user-defined), validation des champs requis, gestion des outils absents.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `DefinitionInvalideError` | `apps/backend/app/services/agent_definitions.py:40` | Le fichier existe mais ne décrit pas un agent exploitable |
| `AgentDefinition` | `apps/backend/app/services/agent_definitions.py:45` | Dataclass d'un agent chargé et validé (slug, name, contract, system_prompt, tools, context, layer, model_hint, quota_tours, builtin, tools_absents) |
| `chemin_de` | `apps/backend/app/services/agent_definitions.py:67` | Rend le chemin `agents/{slug}.yaml` |
| `_texte` | `apps/backend/app/services/agent_definitions.py:71` | Valide qu'un champ YAML est une chaîne non vide |
| `parser` | `apps/backend/app/services/agent_definitions.py:79` | Parse un fichier YAML en `AgentDefinition`, lève `DefinitionInvalideError` |
| `DefinitionRejetee` | `apps/backend/app/services/agent_definitions.py:134` | Dataclass d'un fichier rejeté avec sa raison |
| `_fichiers_agents` | `apps/backend/app/services/agent_definitions.py:140` | Récupère les fichiers YAML du workspace pour un créateur |
| `_slugs_livres` | `apps/backend/app/services/agent_definitions.py:152` | Slugs des agents fournis avec Philum (seed) |
| `lister` | `apps/backend/app/services/agent_definitions.py:160` | Rend (agents valides, fichiers rejetés) |
| `obtenir` | `apps/backend/app/services/agent_definitions.py:187` | Rend l'agent de ce slug, ou None |

## Invariants

- `DOSSIER = "agents/"` (`apps/backend/app/services/agent_definitions.py:29`) : racine des définitions.
- `SLUG_DEFAUT = "assistant"` (`apps/backend/app/services/agent_definitions.py:34`) : slug par défaut quand la session n'en désigne aucun.
- `_SLUG_RE` (`apps/backend/app/services/agent_definitions.py:36`) : kebab-case obligatoire.
- `_LAYERS = ("L0", "L1", "L2", "L3", "L4")` (`apps/backend/app/services/agent_definitions.py:37`) : layers ICM autorisés.

## Dettes

- `_slugs_livres()` (`apps/backend/app/services/agent_definitions.py:152`) : lit le snapshot du seed au moment de l'appel — si le seed change, les slugs changent sans migration.
- `lister()` (`apps/backend/app/services/agent_definitions.py:160`) : appelle `parser()` pour chaque fichier YAML — O(n) sur le nombre de fichiers, acceptable car n est petit.
