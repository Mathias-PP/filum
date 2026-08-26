# 06-01 — conversation.ts (repli SSE→ChatItem)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/agent/conversation.ts` (225 l., 3 symboles).
> sha256: 0ffcd3834fd32fb22467648d9108635dc06e78dcc12ae427728acbdc9df9e252

## Rôle

Pont entre les événements SSE bruts du backend et les `ChatItem` typés du UI. Définit le type `ChatItem` et les fonctions `appliquer()` et `depuisMessages()` qui transforment un flux d'événements en liste de cards affichables (texte, tool_call, tool_result, approval_request).

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ChatItem` | `apps/frontend/src/lib/agent/conversation.ts:12` | Type union des cartes affichables (text, tool, approval) |
| `appliquer` | `apps/frontend/src/lib/agent/conversation.ts:36` | Applique un AgentEvent sur une liste de ChatItem (pure function) |
| `depuisMessages` | `apps/frontend/src/lib/agent/conversation.ts:154` | Convertit un tableau AgentMessage en ChatItem[] pour le UI |

## Invariants

- `appliquer()` (`apps/frontend/src/lib/agent/conversation.ts:36`) : pure function, pas d'effet de bord, déterministe — même input = même output.
- `depuisMessages()` (`apps/frontend/src/lib/agent/conversation.ts:154`) : convertit les messages historiques en ChatItem pour le chargement initial.
- Les `ChatItem` portent un `id` stable pour la clé Svelte (`{#each ... as item (item.id)}`).

## Dettes

- Le typage est loose (types union large) — une dérivation plus stricte des variants pourrait aider le discoverability IDE.
