# 06-11 — chat/+page.svelte (page nouvelle conversation)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/routes/dashboard/chat/+page.svelte` (154 l., 1 symbole).
> sha256: 1fdbe18f9e9e8a83176e292ad4700a379defc8f015a4c59547f7d387d1816f80

## Rôle

Page de navigation pour les conversations agent : sidebar avec la liste des sessions existantes (lien + suppression), zone principale avec le titre de la conversation, l'info du provider par défaut, et le composant `ChatPanel` pour démarrer une nouvelle conversation.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `supprimer` | `apps/frontend/src/routes/dashboard/chat/+page.svelte:38` | Supprime une session via l'API et met à jour la liste locale |

## Invariants

- **Pas de démontage** : `history.replaceState()` (`apps/frontend/src/routes/dashboard/chat/+page.svelte:136`) change l'URL sans naviguer — évite de couper le flux SSE en cours.
- **Gratuit** : `gratuitDisponible` / `gratuitActifIci` déterminent si la bannière de consentement est affichée dans ChatPanel.
- **Provider par défaut** : affiché en haut de page — « Répondra avec <model> (<name>), votre clé, votre facture. »

## Dettes

- `supprimer()` (`apps/frontend/src/routes/dashboard/chat/+page.svelte:38`) : pas de roll-back optimistic — si l'API échoue, la session reste dans la liste.
