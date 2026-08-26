# 06-05 — AgentMarkdown.svelte (rendu markdown)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/components/chat/AgentMarkdown.svelte` (78 l., 1 symbole).
> sha256: a2b29f88e187a16a70097a10b38436991f74ea7b4aae0bdec21f8ae47e1a4887

## Rôle

Composant Svelte qui rend le contenu markdown d'une réponse agent. Utilise `parseMarkdown()` de `markdown.ts` pour convertir le brut en HTML échappé. Aucun `{@html}` — protection XSS garantie par construction.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `AgentMarkdown` | `apps/frontend/src/lib/components/chat/AgentMarkdown.svelte:1` | Composant : prop `content: string`, rendu HTML échappé |

## Invariants

- **Pas de `{@html}`** : le composant utilise le texte brut échappé — aucun risque d'injection via le contenu agent.
- Prop unique : `content: string` — interface minimale, pas d'état interne.

## Dettes

- Pas de gestion des images markdown (syntaxe `![alt](url)`) — volontaire pour éviter les requêtes réseau non vérifiées.
