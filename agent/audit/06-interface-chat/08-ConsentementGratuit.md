# 06-08 — ConsentementGratuit.svelte (bannière consentement)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/components/chat/ConsentementGratuit.svelte` (84 l., 1 symbole).
> sha256: fe576cf96f9a6b177a96c15f9ad754d4caed6acb56b0deb62cd0e2d89019acee

## Rôle

Bannière de consentement pour le mode gratuit. Affiche les conditions d'utilisation du modèle serveur (Z.ai) et demande un accord explicite avant d'autoriser l'envoi de messages.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ConsentementGratuit` | `apps/frontend/src/lib/components/chat/ConsentementGratuit.svelte:1` | Composant : props `version_warning`, `onConsent`, `onDismiss` |

## Invariants

- **Versionné** : `version_warning` côté serveur — si la version change, le consentement est ré-initialisé (re-consentement obligatoire).
- UX binaire : « J'accepte » ou « Non merci » — pas de mode « plus tard ».

## Dettes

- Pas de stockage localStorage du consentement — si l'utilisateur recharge la page, il doit re-consentir.
