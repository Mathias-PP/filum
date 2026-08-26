# Configuration : réglages env de l'agent et de la couche LLM

## apps/backend/app/core/config.py
Lu intégralement : oui (168/168 lignes) · sha256: 74e111d9b11c · date: 2026-08-25

`Settings` est un `pydantic_settings.BaseSettings` : lecture `.env` + environnement, `case_sensitive=True`, `extra="ignore"` (`apps/backend/app/core/config.py:13`). Instance unique via cache.

### Symboles
- `Settings` — `apps/backend/app/core/config.py:12` — porte tous les réglages ci-dessous ; `__init__` appelle `_validate_secrets` après chargement.
- `get_settings` — `apps/backend/app/core/config.py:167` — décoré `@lru_cache` (`apps/backend/app/core/config.py:166`) : une seule instance par process ; changer une variable d'env exige un redémarrage du conteneur.

### Les 15 variables d'env de l'invariant

Règle de comptage G0 (`agent/audit/_core/gen_inventaire.sh:118`) : champs de `Settings` commençant par `agent_` ou `llm_`. Défauts réels :

**Boucle agent**

| Variable | Défaut | Effet |
|---|---|---|
| `agent_max_tours` | `48` | borne de tours d'un run ; 24 était arbitraire et coupait les audits type thrips ; au-delà on compacte et propose une continuation (`apps/backend/app/core/config.py:82`) |
| `agent_max_turn_tokens` | `8192` | garde-fou coût par tour (`apps/backend/app/core/config.py:86`) |
| `agent_web_search_provider` | `""` | `tavily|exa|brave|serper` quand le provider courant n'a pas de grounding natif ; vide = recherche web désactivée (`apps/backend/app/core/config.py:88`) |
| `agent_web_search_api_key` | `""` | clé du provider de recherche ci-dessus |

**Mode découverte (clé serveur sponsorisée, essai sans BYOK)**

| Variable | Défaut | Effet |
|---|---|---|
| `agent_discovery_enabled` | `False` | désactivé par défaut sur toute instance (`apps/backend/app/core/config.py:96`) |
| `agent_discovery_daily_quota_messages` | `10` | messages/jour/créateur (comptés dans `agent_discovery_quota`) |
| `agent_discovery_provider` / `agent_discovery_model` | `deepseek` / `deepseek-chat` | recommandation prod : ToS commercial ~0.27 $/M tokens (`apps/backend/app/core/config.py:95`) |
| `agent_discovery_api_key` | `""` | la clé sponsorisée |

**Mode gratuit (rotation de lanes serveur)**

| Variable | Défaut | Effet |
|---|---|---|
| `agent_gratuit_enabled` | `False` | contrairement à la découverte, exige un consentement explicite : les fournisseurs gratuits peuvent conserver les échanges pour entraîner leurs modèles (`apps/backend/app/core/config.py:102`) |
| `agent_gratuit_daily_quota_messages` | `30` | quota utilisateur/jour |
| `agent_gratuit_zai_api_key` | `""` | clé résolue à la volée pour tout slug `zai*` (primaire + secours) ; jamais en base (cf. docstring de `AgentLane`, `apps/backend/app/models/agent_lane.py:16`) |
| `agent_allow_local_providers` | `False` | self-hosted uniquement : autorise localhost comme base_url de provider ; ne JAMAIS activer sur le SaaS (`apps/backend/app/core/config.py:112`) |

**Voie serveur LLM**

| Variable | Défaut | Effet |
|---|---|---|
| `llm_direct_model` | `""` | sans proxy, le modèle réel qui honore les alias ; renseigné = court-circuite les alias (ADR-035) ; vide = mode proxy LiteLLM (`apps/backend/app/core/config.py:52`) |
| `llm_direct_model_fallbacks` | `""` | modèles de repli séparés par virgules, essayés dans l'ordre sur 429/404 ; le quota gratuit Gemini se compte par modèle et par jour (~20 appels), sans cette liste toute la couche s'éteint au vingtième appel (`apps/backend/app/core/config.py:59`) |

### Hors invariant mais nécessaires

- `litellm_base_url` = `""` — point d'entrée LLM format OpenAI `/chat/completions` ; **vide = couche LLM désactivée**, tous les appels rendent None et l'application tourne à l'identique (dev local, CI) (`apps/backend/app/core/config.py:45`).
- `litellm_master_key` = `""` — Bearer de la voie serveur ; expurgé des messages d'erreur par `_retenir_panne` (`apps/backend/app/services/llm.py:40`).
- `embedding_model` = `gemini-embedding-001` — embeddings tronqués à 768 dims ; changer ce nom périme les vecteurs déjà calculés (`apps/backend/app/core/config.py:66`).
- `grobid_base_url` = `https://zfhxi-grobid.hf.space` — parsing PDF ; le Space officiel est PAUSED, celui-ci est un duplicate réveillable, cold start ~2 min, échec → repli regex local (`apps/backend/app/core/config.py:73`).
- `master_encryption_key` — déchiffre les clés API BYOK (`api_key_enc`) et sert au hashing applicatif (module interface `app.crypto.keygen`).

### Sécurité de démarrage

- `_coerce_async_driver` — `apps/backend/app/core/config.py:116` — réécrit `postgresql://` en `postgresql+asyncpg://` avant validation.
- `_validate_secrets` — `apps/backend/app/core/config.py:125` — fail-hard en production : si ni `debug=True` ni `CI=true`, `session_secret`/`master_encryption_key` vides lèvent un `RuntimeError` avec remédiation (`apps/backend/app/core/config.py:157`) ; en dev/CI ils sont générés aléatoirement (éphémères). Raison documentée dans le docstring : l'ancien comportement « secret aléatoire au démarrage » invalidait toutes les sessions et corrompait le déchiffrement des clés BYOK à chaque restart Railway sans env.
