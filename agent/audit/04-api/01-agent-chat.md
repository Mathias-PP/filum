# Chat SSE — endpoint principal (`agent_chat.py`)

## apps/backend/app/api/v1/endpoints/agent_chat.py
Lu intégralement : oui (404/404 lignes) · sha256: c7c1e303b9fa · date: 2026-08-25

`POST /agent/chat` : un message, un flux SSE. Le serveur rend les événements produits par `boucle()` (lot 2) : `session`, `message_delta`, `tool_call`, `tool_result`, `approval_request`, `approval_resolved`, `done`, `error`, `discovery_active`, `gratuit_actif`.

### Symboles (5)

- `_MARQUEURS_RATE_LIMIT` — `apps/backend/app/api/v1/endpoints/agent_chat.py:53` — 9 chaînes de détection de rate-limit (français + brut) pour poser un cooldown lane après échec fournisseur.
- `_MESSAGE_SURCHARGE_GRATUIT` — `apps/backend/app/api/v1/endpoints/agent_chat.py:67` — message utilisateur quand la lane gratuite échoue (remplace l'erreur technique brute).
- `_echec_fournisseur_gratuit` — `apps/backend/app/api/v1/endpoints/agent_chat.py:74` — True si le texte d'erreur contient un marqueur de rate-limit.
- `get_approver` — `apps/backend/app/api/v1/endpoints/agent_chat.py:83` — fabrique le callback d'approbation : `pour(creator_id)` → `approuver(request_id, tool, args)` → `attendre(request_id, creator_id)`. Surchargeable en test.
- `_sse` — `apps/backend/app/api/v1/endpoints/agent_chat.py:99` — sérialise un événement SSE avec `default=str` (fusible anti-crash : un `datetime` brut dans un tool_result dégrade le champ au lieu de tuer le flux).

### Flux de résolution provider (`chat_agent`, `apps/backend/app/api/v1/endpoints/agent_chat.py:111`)

Ordre de résolution : provider explicite du body → mode gratuit consenti (lane active) → provider par défaut (`resoudre_defaut`) → mode découverte (`discovery_est_actif` → `resoudre_provider_decouverte`) → erreur « Aucune clé IA disponible ».

**Si pas de `session_id`** : crée une session, titre dérivé du premier message. **Si `session_id` fourni** : lit l'historique persisté (fait autorité, le client ne peut pas le retoucher en route), met à jour `agent_slug` si changé.

### `gen()` — `apps/backend/app/api/v1/endpoints/agent_chat.py:246`

Générateur SSE async. Patterns notables :
- `emit_surveille` (`:266`) intercepte les erreurs `error` en mode gratuit pour traduire en message actionnable ; signale l'échec à la lane via `signaler_echec`.
- `runner()` (`:277`) appelle `boucle()` ; `finally: await queue.put(None)` signale la fin même en cas d'exception.
- `finally: task.cancel()` (`:349`) coupe la boucle si le client ferme l'onglet : sans elle, la boucle continuerait jusqu'à 24 tours en facturant le provider via une session DB déjà fermée.
- `usage_capture` (`:249`) capture les tokens depuis l'événement `done` pour les persister.

### `_persister_tour` — `apps/backend/app/api/v1/endpoints/agent_chat.py:358`

Écrit le tour en append-only dans l'ordre réel : les tool_calls d'abord, la réponse texte finale ensuite (elle est émise en `message_delta` mais absente de `messages` pendant la boucle). Les tokens `prompt_tokens`/`completion_tokens` sont extraits de `usage` et validés (int > 0) avant persiste.
