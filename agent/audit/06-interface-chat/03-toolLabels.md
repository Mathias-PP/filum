# 06-03 — toolLabels.ts (traduction noms d'outils)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/agent/toolLabels.ts` (181 l., 1 symbole).
> sha256: 8f99e0817400cc08f7749e90aeda17bde8221251f5e74c89bd778ad69deab624

## Rôle

Mappe les noms techniques des outils MCP (ex: `search_web`, `add_source`) en labels人文 français lisibles pour l'utilisateur. Utilisé par `ToolCard` et `ChatPanel` pour afficher les actions de l'agent en langage naturel.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `rendreOutil` | `apps/frontend/src/lib/agent/toolLabels.ts:156` | Mappe `(name, args, result)` → `{ action, objet }` en français |

## Invariants

- `rendreOutil()` (`apps/frontend/src/lib/agent/toolLabels.ts:156`) : si l'inconnu n'est pas dans la map, retourne le nom brut comme action — pas d'erreur.
- La map couvre les 43 outils MCP + les 2 outils STARTER (`recall_memory`, `rebuild_graph`).

## Dettes

- La map est en dur dans le fichier — tout ajout d'outil côté backend nécessite une mise à jour同步 du frontend.
