# 06-07 — ChatPanel.svelte (panneau chat principal)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/components/chat/ChatPanel.svelte` (1007 l., 19 symboles).
> sha256: a7f6fe86917562656cfb648fc0cedd4aee17ad17a02757e8e4b2e51aa7b29a64

## Rôle

Le composant central du chat agent. Gère le flux SSE en streaming, l'affichage des messages (texte + tool calls + approvals), la sélection de provider, le consentement mode gratuit, et l'envoi de messages. C'est le plus gros fichier du lot (1 007 LOC).

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ChatPanel` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Composant principal : props `sessionId?`, `titreInitial?`, `onsession?` |
| `messages` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : liste des ChatItem affichés |
| `input` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : texte brut de l'input utilisateur |
| `sending` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : true pendant l'envoi SSE |
| `provider` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : provider sélectionné (ou null = default) |
| `consentRequired` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : true si le consentement gratuit est requis |
| `consentGiven` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : true après consentement |
| `streamingText` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : texte en cours de streaming (avant commit final) |
| `currentToolCalls` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : tool calls en cours (avant tool_result) |
| `approvalPending` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : approval en attente (ou null) |
| `autoScroll` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | State : true si l'utilisateur est en bas de page |
| `envoyer` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : envoie le message et consomme le flux SSE |
| `gererEvenement` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : dispatch un SSEEvent en mutation de state |
| `defilerVersLeBas` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : scroll automatique si en bas |
| `handleScroll` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : détecte si l'utilisateur est en bas de page |
| `handleKeydown` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : Enter pour envoyer, Shift+Enter pour newline |
| ` creerSession` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : crée une session si pas de sessionId |
| `activerGratuit` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : active le mode gratuit et re-consent |
| `demanderConsentement` | `apps/frontend/src/lib/components/chat/ChatPanel.svelte:1` | Fonction : vérifie si le consentement gratuit est nécessaire |

## Invariants

- **SSE streaming** : `envoyer()` (`apps/frontend/src/lib/components/chat/ChatPanel.svelte:1`) consomme le `ReadableStream` événement par événement — pas de `await response.json()`.
- **Auto-scroll** : `defilerVersLeBas()` (`apps/frontend/src/lib/components/chat/ChatPanel.svelte:1`) ne scrolle que si l'utilisateur est déjà en bas — ne déroge jamais le focus.
- **Consentement gratuit** : `demandeConsentement()` (`apps/frontend/src/lib/components/chat/ChatPanel.svelte:1`) vérifie `gratuit.etat()` au montage — si `actif` et pas de `consentGiven`, affiche la bannière.
- **Provider sélection** : si aucun provider par défaut et pas de consentement gratuit, le chat reste utilisable (mode découverte serveur).

## Dettes

- **1 007 LOC** : gros fichier qui gère SSE, UI, consentement, provider selection — pourrait bénéficier d'une décomposition en sous-composants.
- **`currentToolCalls`** : accumule les tool_calls en cours mais ne gère pas les cas où un tool_call est annulé (pas de SSE event d'annulation).
- **`autoScroll`** : logique fragile — si l'utilisateur scrolle légèrement en bas mais pas tout à fait, le scroll auto ne se déclenche pas.
