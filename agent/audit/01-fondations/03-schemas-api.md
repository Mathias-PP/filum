# Contrats d'API de l'agent : schémas Pydantic

Validation d'entrée / forme de sortie des endpoints agent (montés en lot 4). Tous héritent des garde-fous Pydantic ; les modèles d'entrée utilisent systématiquement `extra="forbid"` (champ inconnu = 422, pas silence).

## apps/backend/app/schemas/agent_chat.py
Lu intégralement : oui (137/137 lignes) · sha256: 35500ecaac8f · date: 2026-08-25

Deux modes coexistent documentés en tête : avec `session_id` l'historique vient de la base ; sans, le client envoie `history` et conserve lui-même (`apps/backend/app/schemas/agent_chat.py:1`). Bornes anti-gonflement dans les deux cas.

### Symboles
- `AgentChatMessage` — `apps/backend/app/schemas/agent_chat.py:18` — un message d'historique client : `role` limité à `user|assistant`, `content` 1→200 000 chars stripé (validateur `_strip`, ligne 24).
- `AgentChatRequest` — `apps/backend/app/schemas/agent_chat.py:33` — payload du POST chat : `message` ≤200k stripé, `history` ≤40 messages (`apps/backend/app/schemas/agent_chat.py:37`), `session_id` (absent → session créée, son id arrive dans l'événement `session`), `provider_id` (null = défaut), `model_override` ≤120, `agent_slug` pattern kebab-case ≤80 (`apps/backend/app/schemas/agent_chat.py:52`) — null = agent attaché à la session sinon généraliste.
- `AgentSessionCreate` — `apps/backend/app/schemas/agent_chat.py:69` — création manuelle de session : `title` ≤200, `provider_id`, `agent_slug`.
- `AgentSessionUpdate` — `apps/backend/app/schemas/agent_chat.py:77` — patch partiel des trois mêmes champs (+ `model_override`).
- `AgentSessionRead` — `apps/backend/app/schemas/agent_chat.py:86` — sortie liste/détail sessions (`from_attributes=True`).
- `AgentMessageRead` — `apps/backend/app/schemas/agent_chat.py:98` — sortie journal : expose `tool_calls`, `tool_name` et surtout `tool_call_id` (`apps/backend/app/schemas/agent_chat.py:109`) — le front en a besoin pour rejouer une session sans afficher deux fois chaque outil (sinon l'appel orphelin resterait « En cours… » à jamais).
- `AgentFicheRequest` — `apps/backend/app/schemas/agent_chat.py:113` — lancement d'un run de fiche : `content_url` ≤2000, `slug` kebab-case ≤120, `depuis` = reprise à un étage donné (les comptes rendus déjà écrits servent de contexte).
- `AgentApprovalDecision` — `apps/backend/app/schemas/agent_chat.py:127` — réponse d'approbation humaine : `request_id` ≤64 + booléen `approved`.
- `AgentSessionUsage` — `apps/backend/app/schemas/agent_chat.py:134` — agrégat tokens/coût EUR nullable pour GET usage.

## apps/backend/app/schemas/agent_definition.py
Lu intégralement : oui (43/43 lignes) · sha256: 547c52dacb8d · date: 2026-08-25

Lecture seule par construction : un agent nommé EST un fichier du workspace, l'écrire = écrire son fichier via `PUT /agent/workspace/file` (`apps/backend/app/schemas/agent_definition.py:1`). Pas de Create/Update ici.

### Symboles
- `AgentDefinitionRead` — `apps/backend/app/schemas/agent_definition.py:13` — vue d'un agent nommé : `slug`, `name`, `contract`, `system_prompt`, `tools` autorisés, `context`, `layer`, `model_hint`, `builtin` (livré avec Philum, « Restaurer template » peut le recréer), `tools_absents` (outils demandés que le serveur n'expose pas aujourd'hui), `path` (pour ouvrir l'éditeur).
- `AgentDefinitionRejected` — `apps/backend/app/schemas/agent_definition.py:32` — un fichier de `agents/` inexploitable : `path` + `raison`.
- `AgentDefinitionList` — `apps/backend/app/schemas/agent_definition.py:39` — `agents` + `rejected` ; les rejets sont rendus au client pour que le créateur voie ses fichiers cassés au lieu d'une disparition silencieuse dans le sélecteur.

## apps/backend/app/schemas/agent_provider.py
Lu intégralement : oui (193/193 lignes) · sha256: 17b0c12ec92a · date: 2026-08-25

Contrats BYOK des providers.

Constantes de référence :

- `ProviderKind` — `apps/backend/app/schemas/agent_provider.py:10` — enum : openai, anthropic, deepseek, gemini, groq, openrouter, mistral, cerebras, custom.
- `PROVIDER_DEFAULT_BASE_URLS` — `apps/backend/app/schemas/agent_provider.py:24` — racines par défaut résolues **à la création** et stockées NOT NULL en base ; Gemini expose sa surface OpenAI sous `/v1beta/openai`.
- `MODELES_SUGGERES` — `apps/backend/app/schemas/agent_provider.py:38` — filet de secours si `/models` ne répond pas ; PAS la source de vérité (la liste vivante vient de `lister_modeles()`, vérifiée 2026-08-21).
- `MODELES_RECOMMANDES` — `apps/backend/app/schemas/agent_provider.py:52` — sous-ensemble affiché avec badge UI.

### Symboles
- `_api_key_masked` — `apps/backend/app/schemas/agent_provider.py:65` — forme affichable `sk-…1234` ; ne renvoie jamais la clé en clair.
- `_base_url_normalise` — `apps/backend/app/schemas/agent_provider.py:72` — nettoyage syntaxique (http(s), hôte présent, sans slash final). L'assainissement complet (DNS, blocage adresses privées) se fait dans le service car il exige du réseau (`apps/backend/app/schemas/agent_provider.py:75`).
- `AgentProviderCreate` — `apps/backend/app/schemas/agent_provider.py:89` — entrée : kind, display_name ≤80, base_url ≤300 normalisée, model ≤120, api_key ≤500, is_default. Validateurs stripeurs sur api_key/model/base_url.
- `AgentProviderUpdate` — `apps/backend/app/schemas/agent_provider.py:123` — même forme, tout optionnel (PATCH).
- `AgentProviderRead` — `apps/backend/app/schemas/agent_provider.py:160` — sortie : jamais la clé, toujours `api_key_masked`.
- `AgentProviderTestResult` — `apps/backend/app/schemas/agent_provider.py:174` — résultat du test de clé : `ok`, `http_status`, `model_resolved`, `url`, `message`, `provider_message` (texte brut du fournisseur — souvent la seule information exploitable : Gemini y nomme le modèle de remplacement, OpenAI y distingue crédit épuisé de limite de débit ; ne JAMAIS le remplacer par une reformulation), `latency_ms`, `models` (sur test réussi la liste des modèles du compte est chargée en même temps → dropdown chaud, cache serveur 15 min peuplé sans second appel).
