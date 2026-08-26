# 01 — Fondations : config, données, transport LLM

> Fiches du lot 1 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G1** (`check_lot.sh 1`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt) gelé au commit `444ef68`.

## Rôle du domaine

Le socle sur lequel tout le reste de l'agent repose :

1. **Réglages** (`core/config.py`) — toutes les variables d'environnement `agent_*`/`llm_*`, leurs défauts et leur effet.
2. **Données** (`models/agent_*.py` ×4, migrations 040→052) — le schéma PostgreSQL de l'agent : providers BYOK chiffrés, sessions/messages append-only, quotas découverte, lanes gratuites + consentements.
3. **Contrats d'API** (`schemas/agent_*.py` ×3) — ce que le front peut envoyer et recevoir.
4. **Transport LLM** (`services/llm.py`, `services/llm_adapters.py`) — les deux voies d'appel aux modèles : voie serveur (proxy LiteLLM, alias de tâche) et voie BYOK (protocoles OpenAI-compat / Anthropic natif).

## Les fichiers

| Fiche | Contenu | Fichiers couverts |
|---|---|---|
| [01-donnees.md](01-donnees.md) | Schéma de données complet : qui écrit quoi, contraintes, historique des migrations | 4 modèles + 8 migrations |
| [02-config-env.md](02-config-env.md) | Les réglages env avec défauts réels et effet | `config.py` |
| [03-schemas-api.md](03-schemas-api.md) | Payloads acceptés/rendus, bornes de validation | 3 schémas |
| [04-transport-llm.md](04-transport-llm.md) | Chaîne provider : alias, URL, erreurs, conversion Anthropic | `llm.py`, `llm_adapters.py` |

## Invariants du lot (à retrouver à l'identique par G1)

- **15 variables d'environnement** (règle de comptage `_core/gen_inventaire.sh:118` : champs `Settings` commençant par `agent_`, `llm_`) : 13 `agent_*` + `llm_direct_model` + `llm_direct_model_fallbacks`. `litellm_base_url`/`litellm_master_key` sont hors invariant mais documentés ([02-config-env.md](02-config-env.md)).
- **8 migrations agent** : chaîne linéaire `040→(042)→(045)→(046)→(047)→(049)→(051)→052` (les intermédiaires 041/044/048/050 sont hors périmètre agent).
- **5 tables PostgreSQL possédées par l'agent** : `agent_providers`, `agent_sessions`, `agent_messages`, `agent_discovery_quota`, `agent_lanes` + `agent_lane_usage` + `agent_gratuit_consents` (= 7 tables au total).
- **3 alias de tâche LLM** côté serveur : `biblio-parse`, `excerpt-suggest`, `metadata-extract`.
- **2 protocoles BYOK** : openai-compat (8 kinds) et anthropic natif (1 kind).

## Dettes et pièges constatés à la lecture

- Le nommage est trompeur : la « voie serveur » vit encore sous le préfixe `litellm_*` alors qu'elle vise aujourd'hui n'importe quelle racine OpenAI-compatible, proxy ou provider direct (`apps/backend/app/core/config.py:45`).
- La contrainte « un seul provider par défaut » est applicative, pas SQL (`apps/backend/alembic/versions/040_agent_providers.py:13`) : un bug dans le service pourrait créer deux défauts sans que la base refuse.
- `agent_messages.tool_call_id` est nullable pour rétrocompatibilité ; les sessions antérieures à cette colonne ne peuvent pas être reprises sur Gemini (HTTP 400) (`apps/backend/app/models/agent_session.py:71`).
