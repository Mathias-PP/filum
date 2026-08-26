# 06-12 — chat/[id]/+page.svelte (page conversation existante)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte` (96 l., 2 symboles).
> sha256: 51c9a068da369d10ea79375d4e26609398dc4d864b2026cfc78d1e53294231a5

## Rôle

Page d'une conversation existante : charge le titre depuis l'API, affiche le composant `ChatPanel` avec le `sessionId`, et permet le renommage inline (clic sur le crayon, input + validation).

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ouvrirEdition` | `apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte:26` | Passe en mode édition du titre (affiche l'input) |
| `renommer` | `apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte:31` | Envoie le nouveau titre à l'API et met à jour le state |

## Invariants

- **Renommage** : `renommer()` (`apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte:31`) vérifie `brouillon.trim()` — titre vide = abandon silencieux.
- **Re-chargement** : `$effect()` (`apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte:15`) réagit au changement de `sessionId` (navigation entre conversations).
- **Escape** : l'input de renommage se ferme sur Escape sans sauvegarder.

## Dettes

- Pas de debounce sur le renommage — si l'utilisateur clique rapidement sur OK après avoir tapé, le dernier appel gagne.
