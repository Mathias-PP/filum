# 06-10 — agents/+page.svelte (page gestion clés API)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/routes/dashboard/agents/+page.svelte` (486 l., 9 symboles).
> sha256: 3a05f7220681bd4c0c3ecb89c56288e112307d736d809eb87ce857fa89ac57b2

## Rôle

Page complète de gestion des clés API (BYOK) : liste des providers enregistrés, formulaire d'ajout/édition avec sélection de fournisseur et de modèle, test de clé, définition par défaut, suppression avec confirmation. Le cœur de l'expérience utilisateur pour brancher son propre modèle.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `kinds` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:14` | Constante : liste des ProviderKind avec labels |
| `MODELES_SUGGERES` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:26` | Constante : modèles suggérés par fournisseur |
| `resetForm` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:78` | Réinitialise le formulaire à ses valeurs par défaut |
| `openForm` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:91` | Ouvre le formulaire en mode création |
| `ouvrirEdition` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:96` | Ouvre le formulaire en mode édition |
| `chargerModeles` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:108` | Appelle l'API pour lister les modèles du provider |
| `submit` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:119` | Soumet le formulaire (create ou update) |
| `definirDefaut` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:158` | Marque un provider comme par défaut |
| `tester` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:167` | Teste la clé API (appel minimal au fournisseur) |
| `demanderSuppression` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:178` | Ouvre la boîte de confirmation suppression |
| `supprimer` | `apps/frontend/src/routes/dashboard/agents/+page.svelte:183` | Supprime le provider et rafraîchit la liste |

## Invariants

- **Clé masquée** : `api_key_masked` ne montre jamais la clé en clair — le champ édition est vide par défaut ("Laisser vide pour conserver la clé actuelle").
- **Fournisseurs** : 9 kinds supportés (openai, anthropic, gemini, mistral, groq, openrouter, cerebras, deepseek, custom).
- **Modèles** : `MODELES_SUGGERES` contient les modèles recommandés par fournisseur — l'utilisateur peut aussi saisir un nom libre.

## Dettes

- **486 LOC** : page CRUD complète en un seul fichier — pourrait bénéficier d'une extraction du formulaire en sous-composant.
- `chargerModeles()` (`apps/frontend/src/routes/dashboard/agents/+page.svelte:108`) : n'est appelé qu'en mode édition — pas d'auto-détection du modèle courant.
