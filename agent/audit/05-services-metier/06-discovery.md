# 05-06 — Discovery (clé serveur, quota découverte, transient)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_discovery.py` (142 l., 8 symboles).
> **SHA256 :** `7fba2a223658c059d98b54f6eebafdeeac5f8a572cdbf9f87caf01342b15cdf6`

## Rôle

Mode découverte : clé serveur DeepSeek sponsorisée, quota quotidien, provider transient (non persisté). Permet de tester l'agent sans clé personnelle.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ErreurQuota` | `apps/backend/app/services/agent_discovery.py:27` | Exception quand le quota quotidien est épuisé |
| `discovery_est_actif` | `apps/backend/app/services/agent_discovery.py:36` | Vérifie si le mode découverte est activé ET a une clé |
| `_provider_base_url` | `apps/backend/app/services/agent_discovery.py:41` | Rend l'URL de base d'un provider depuis les constantes |
| `_chiffrer_cle_placeholder` | `apps/backend/app/services/agent_discovery.py:45` | Chiffre la clé serveur pour construire un provider transient |
| `resoudre_provider_decouverte` | `apps/backend/app/services/agent_discovery.py:54` | Construit un `AgentProvider` transient portant la clé serveur |
| `nom_public_provider` | `apps/backend/app/services/agent_discovery.py:75` | Rend le nom d'affichage du provider de découverte |
| `verifier_quota` | `apps/backend/app/services/agent_discovery.py:88` | Vérifie le quota du jour, lève `ErreurQuota` si dépassé |
| `consommer_message` | `apps/backend/app/services/agent_discovery.py:109` | Incrémente atomiquement le compteur quotidien |

## Invariants

- `AgentDiscoveryQuota` (`apps/backend/app/models/agent_discovery_quota.py:21`) : modèle de la table du quota.
- `discovery_est_actif()` (`apps/backend/app/services/agent_discovery.py:36`) : doit être `True` ET avoir une clé serveur configurée.
- `resoudre_provider_decouverte()` (`apps/backend/app/services/agent_discovery.py:54`) : NE PAS insérer en base — provider valable le temps d'un seul appel.
- `verifier_quota()` (`apps/backend/app/services/agent_discovery.py:88`) : SELECT + UPDATE/UPDATE séquentiel, compatible SQLite (tests) et Postgres (prod).

## Dettes

- `consommer_message()` (`apps/backend/app/services/agent_discovery.py:109`) : pas de vrai atomique cross-process, le quota est indicatif.
- Le mode découverte partage le compteur `AgentDiscoveryQuota` avec le mode gratuit mais a des plafonds distincts dans les settings.
