# 05-06 — Discovery (clé serveur, quota découverte, transient)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_discovery.py` (142 l., 8 symboles).

## Rôle

Mode découverte : clé serveur DeepSeek sponsorisée, quota quotidien, provider transient (non persisté). Permet de tester l'agent sans clé personnelle.

## Architecture

- `AgentDiscoveryQuota` : modèle de quota (clé serveur, quota restant, date de réinitialisation).
- `_QUOTA_KEY` : clé Redis pour le quota découverte.
- `_QUOTA_MAX` : quota max configurable (défaut 50).
- `_QUOTA_RESET_HOUR` : heure de réinitialisation du quota (00:00 UTC).

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `AgentDiscoveryQuota` | 12 | Modèle quota |
| `_QUOTA_KEY` | 22 | Clé Redis |
| `_QUOTA_MAX` | 25 | Quota max (50) |
| `_QUOTA_RESET_HOUR` | 28 | Heure reset (00:00) |
| `DiscoveryError` | 33 | Exception métier |
| `resoudre_discovery` | 40 | Orchestrateur principal |
| `_decremente_quota` | 80 | Décrémente quota |
| `_quota_restant` | 100 | Calcule quota restant |

## Flux typique (resolution discovery)

1. `resoudre_discovery` → vérifie si la clé serveur DeepSeek est configurée.
2. Si oui : vérifie le quota restant → si quota > 0 : retourne le provider transient avec la clé serveur.
3. Si quota = 0 : lève `DiscoveryError` avec un message explicite.
4. `_decremente_quota` → incrémente le compteur Redis.

## Dettes et pièges

- `_QUOTA_MAX=50` (`apps/backend/app/services/agent_discovery.py:25`) : quota par défaut — configurable via settings, ne pas modifier sans test.
- `_QUOTA_RESET_HOUR=0` (`apps/backend/app/services/agent_discovery.py:28`) : réinitialisation à 00:00 UTC — ne pas modifier sans impact timezone.
- Le mode découverte partage le compteur `AgentDiscoveryQuota` avec le mode gratuit mais a des plafonds distincts dans les settings.
- `resoudre_discovery` (`apps/backend/app/services/agent_discovery.py:40`) : ne lève jamais sur succès — retourne un provider transient non persisté.
