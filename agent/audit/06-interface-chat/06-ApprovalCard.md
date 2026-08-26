# 06-06 — ApprovalCard.svelte (approbation outil)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/components/chat/ApprovalCard.svelte` (80 l., 1 symbole).
> sha256: da3eb8d730918e6b944c93c8ddc46dcff3fbb730667bf5744aed09e4ccc041c5

## Rôle

Composant d'approbation binaire pour les outils qui nécessitent une validation utilisateur avant exécution (consentement). Affiche le nom de l'action et deux boutons (Approuver / Refuser).

## Symboles

| Symboles | Ligne | Rôle |
|---|---|---|
| `ApprovalCard` | `apps/frontend/src/lib/components/chat/ApprovalCard.svelte:1` | Composant : props `action`, `onApprove`, `onReject` |

## Invariants

- UX binaire : pas de mode « ajourner » — l'utilisateur doit trancher maintenant ou le tour est interrompu.
- Les callbacks `onApprove`/`onReject` sont passées par le parent (ChatPanel) et ne font qu'un setter de state.

## Dettes

- Pas de délai d'expiration côté client — si l'utilisateur ne clique pas, la card reste affichée indéfiniment.
