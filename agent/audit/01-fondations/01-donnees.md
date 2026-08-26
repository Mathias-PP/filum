# Données de l'agent : modèles SQLAlchemy et migrations

## Vue d'ensemble du schéma

Sept tables appartenant à l'agent, créées par les migrations 040→052 :

```
users ──CASCADE──< agent_providers <──SET NULL── agent_sessions ──CASCADE──< agent_messages

   (aucune FK)
creator_id ──< agent_discovery_quota      agent_lanes ──< agent_lane_usage
creator_id ─── agent_gratuit_consents (PK = creator_id)
```

Doctrine transversale : `agent_messages` est **append-only** — jamais d'UPDATE, car un message réécrit ferait mentir la trace sur ce que le modèle avait sous les yeux (`apps/backend/alembic/versions/042_agent_sessions.py:8`, `apps/backend/app/models/agent_session.py:52`).

---

## apps/backend/app/models/agent_provider.py
Lu intégralement : oui (57/57 lignes) · sha256: ee1c748604e7 · date: 2026-08-25

Table `agent_providers` — un compte IA enregistré par un créateur (BYOK).

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | défaut `uuid4` (`apps/backend/app/models/agent_provider.py:23`) |
| `creator_id` | UUID FK→users.id CASCADE, indexé | supprimer le compte efface ses clés (`apps/backend/app/models/agent_provider.py:28`) |
| `provider` | String(20) | kind (`openai`, `anthropic`, …) |
| `display_name` | String(80) NOT NULL | |
| `base_url` | String(300) NOT NULL | résolue au défaut du provider à la création |
| `model` | String(120) NOT NULL | |
| `api_key_enc` | Text NOT NULL | AES-GCM via `master_encryption_key`, jamais en clair (`apps/backend/app/models/agent_provider.py:38`) |
| `is_default` | Boolean NOT NULL | un seul par créateur, contrainte applicative |
| `created_at`/`updated_at` | DateTime | `server_default=func.now()` / `onupdate` |

Contrainte d'unicité `(creator_id, provider, base_url, model)` (`apps/backend/app/models/agent_provider.py:46`) : rend impossible un doublon exact chez un même créateur ; c'est la raison pour laquelle `base_url` est NOT NULL même pour les providers intégrés (des NULL distincts auraient cassé l'unicité PostgreSQL).

### Symboles
- `AgentProvider` — `apps/backend/app/models/agent_provider.py:13` — modèle ORM de la table ; aucun effet de bord propre (le chiffrement de la clé se fait dans le service, pas ici). `__repr__` sans secret (`apps/backend/app/models/agent_provider.py:56`).

---

## apps/backend/app/models/agent_session.py
Lu intégralement : oui (89/89 lignes) · sha256: fd353a8993db · date: 2026-08-25

Deux modèles : la conversation et sa trace.

### Symboles
- `AgentSession` — `apps/backend/app/models/agent_session.py:18` — table `agent_sessions` : `creator_id` (FK CASCADE indexé), `title` (défaut ""), `provider_id` (FK→agent_providers **SET NULL** : retirer une clé ne doit pas effacer l'historique), `model_override`, `agent_slug` (agent nommé attaché, NULL = généraliste), `created_at`/`updated_at`, `last_message_at`, `deleted_at` (suppression logique).
- `AgentMessage` — `apps/backend/app/models/agent_session.py:51` — table `agent_messages` : `role` (`user|assistant|tool|system`), `content` Text, `tool_calls` JSON(B), `tool_name`, `tool_call_id`, `prompt_tokens`/`completion_tokens`, `created_at`.

Détails portés par le code :

- `_JSON_LIST` (`apps/backend/app/models/agent_session.py:15`) : JSON portable avec variante JSONB sous PostgreSQL (indexable) — les tests SQLite passent grâce au variant.
- `tool_call_id` nullable (`apps/backend/app/models/agent_session.py:76`) : requis par la spec OpenAI sur les messages rôle `tool` ; Gemini rejette en HTTP 400 `INVALID_ARGUMENT` sans lui. Nullable pour rétrocompatibilité des vieilles lignes.
- `created_at` horodaté côté Python (`apps/backend/app/models/agent_session.py:82`) : `now()` SQL est figé sur la transaction et à précision moteur ; deux messages d'un même tour ne doivent jamais être ex æquo dans le journal → default Python `datetime.now(UTC)` naïf + `server_default` en filet.

---

## apps/backend/app/models/agent_discovery_quota.py
Lu intégralement : oui (21/21 lignes) · sha256: ca7b528f9c32 · date: 2026-08-25

Compteur quotidien du mode découverte (clé sponsorisée Philum).

### Symboles
- `AgentDiscoveryQuota` — `apps/backend/app/models/agent_discovery_quota.py:12` — table `agent_discovery_quota` : `creator_id` String indexé (pas une FK — cohérent avec les autres compteurs), `date`, `messages_used`. Unique `(creator_id, date)` (`apps/backend/app/models/agent_discovery_quota.py:14`) : une seule ligne comptable par créateur et par jour.

---

## apps/backend/app/models/agent_lane.py
Lu intégralement : oui (66/66 lignes) · sha256: 44d104ea30a4 · date: 2026-08-25

Trois modèles du mode gratuit (rotation de lanes serveur).

### Symboles
- `AgentLane` — `apps/backend/app/models/agent_lane.py:12` — table `agent_lanes` : couple (fournisseur, modèle) serveur. `slug` unique (`apps/backend/app/models/agent_lane.py:24`) sert à retrouver la clé en settings (`agent_gratuit_<slug>_api_key`) ; **la clé ne vit jamais en base**, une lane sans clé configurée est ignorée par le routeur. `label_public` pour la bannière UI, `provider_kind` (« custom » = OpenAI-compatible avec base_url), `base_url`, `model`, `rpm_cap`/`rpd_cap` plafonds optionnels, `actif`, `position` (ordre de rotation).
- `AgentLaneUsage` — `apps/backend/app/models/agent_lane.py:37` — compteur quotidien par lane : `requests_used`, `cooldown_until` posé sur un 429 pour écarter la lane pendant la fenêtre au lieu de marteler l'endpoint (`apps/backend/app/models/agent_lane.py:40`). Unique `(lane_id, date)` (`apps/backend/app/models/agent_lane.py:45`).
- `AgentGratuitConsent` — `apps/backend/app/models/agent_lane.py:54` — consentement explicite de l'utilisateur : PK = `creator_id` (une ligne par créateur, reconsentir écrase), `version` du texte de warning, `consent_at`. Une montée de version force un nouveau consentement.

Effets de bord : aucun (ORM pur) ; écrits par les services des lots 2/5.

---

## Migrations Alembic (040 → 052)

Chaîne linéaire, chaque fichier porte `revision` + `down_revision`. Les symboles `upgrade`/`downgrade` de chaque fichier sont documentés ci-dessous.

### apps/backend/alembic/versions/040_agent_providers.py
Lu intégralement : oui (93/93 lignes) · sha256: 83a6e5b7ea70 · date: 2026-08-25

Crée `agent_providers` (colonnes commentées dans le code). `base_url` NOT NULL pour rendre l'unicité exploitable sans piège des NULL distincts (`apps/backend/alembic/versions/040_agent_providers.py:8`) ; `is_default` sans contrainte partielle SQL — le service efface les autres avant d'en poser un (`apps/backend/alembic/versions/040_agent_providers.py:13`). Index `ix_agent_providers_creator_id`.
- `upgrade` — `apps/backend/alembic/versions/040_agent_providers.py:35` — création table + index.
- `downgrade` — `apps/backend/alembic/versions/040_agent_providers.py:91` — drop index puis table.

### apps/backend/alembic/versions/042_agent_sessions.py
Lu intégralement : oui (105/105 lignes) · sha256: 1dff99059aad · date: 2026-08-25

Crée `agent_sessions` + `agent_messages`. Doctrine append-only inscrite dans le docstring (`apps/backend/alembic/versions/042_agent_sessions.py:8`). `title` server_default "", `provider_id` SET NULL, `deleted_at` suppression logique (`apps/backend/alembic/versions/042_agent_sessions.py:59`). `tool_calls` en JSONB natif ici (`apps/backend/alembic/versions/042_agent_sessions.py:84`) — le variant JSON n'existe que côté modèle. Index sur les deux `*_id`.
- `upgrade` — `apps/backend/alembic/versions/042_agent_sessions.py:31` — deux create_table + deux index.
- `downgrade` — `apps/backend/alembic/versions/042_agent_sessions.py:101` — drop dans l'ordre inverse.

### apps/backend/alembic/versions/045_agent_message_usage.py
Lu intégralement : oui (37/37 lignes) · sha256: c3b87831c546 · date: 2026-08-25

Ajoute `prompt_tokens`/`completion_tokens` (Integer nullables) sur `agent_messages` pour agréger le coût d'une session via GET usage.
- `upgrade` — `apps/backend/alembic/versions/045_agent_message_usage.py:24` — deux add_column.
- `downgrade` — `apps/backend/alembic/versions/045_agent_message_usage.py:35` — drop inverse.

### apps/backend/alembic/versions/046_agent_discovery_quota.py
Lu intégralement : oui (44/44 lignes) · sha256: 5470dadfe049 · date: 2026-08-25

Crée `agent_discovery_quota` avec unique `uq_discovery_quota_creator_date` (`apps/backend/alembic/versions/046_agent_discovery_quota.py:33`), index creator_id.
- `upgrade` — `apps/backend/alembic/versions/046_agent_discovery_quota.py:25` — create_table + index.
- `downgrade` — `apps/backend/alembic/versions/046_agent_discovery_quota.py:42` — drop index + table.

### apps/backend/alembic/versions/047_agent_session_model_override.py
Lu intégralement : oui (32/32 lignes) · sha256: a797325e76b6 · date: 2026-08-25

Ajoute `agent_sessions.model_override` String(120) nullable — choisir un modèle différent de `provider.model` pour une session sans muter le provider global ; NULL = `provider.model`.
- `upgrade` — `apps/backend/alembic/versions/047_agent_session_model_override.py:24`
- `downgrade` — `apps/backend/alembic/versions/047_agent_session_model_override.py:31`

### apps/backend/alembic/versions/049_agent_session_agent_slug.py
Lu intégralement : oui (34/34 lignes) · sha256: eca33dc22857 · date: 2026-08-25

Ajoute `agent_sessions.agent_slug` String(80) nullable. Pas de clé étrangère volontairement : la définition vit dans le workspace (`agents/<slug>.yaml`), pas en base, et un slug orphelin doit dégrader vers le généraliste plutôt que casser la session (`apps/backend/alembic/versions/049_agent_session_agent_slug.py:7`).
- `upgrade` — `apps/backend/alembic/versions/049_agent_session_agent_slug.py:29`
- `downgrade` — `apps/backend/alembic/versions/049_agent_session_agent_slug.py:33`

### apps/backend/alembic/versions/051_mode_gratuit.py
Lu intégralement : oui (120/120 lignes) · sha256: 0b6bbbc98ab8 · date: 2026-08-25

Crée les trois tables du mode gratuit (`agent_lanes`, `agent_lane_usage`, `agent_gratuit_consents`) et sème la lane Z.ai primaire : slug `zai`, label « GLM · Z.ai », base `https://api.z.ai/api/paas/v4`, modèle `glm-4.7-flash`, rpm_cap 3, rpd_cap 900 (volontairement sous le plafond réel ~1000/jour), position 0 (`apps/backend/alembic/versions/051_mode_gratuit.py:98`). Deux enseignements consignés dans le fichier :
- Histoire des deux têtes Alembic (née en parallèle de `050_card_kind`, conteneur redémarré en boucle sur `upgrade head`) ; replace derrière 050 plutôt qu'une revision de jonction qui aurait rendu `downgrade -1` ambigu (`apps/backend/alembic/versions/051_mode_gratuit.py:12`).
- `bulk_insert` typé plutôt qu'INSERT texte : PostgreSQL refuse une chaîne dans une colonne uuid là où SQLite l'accepte (`apps/backend/alembic/versions/051_mode_gratuit.py:80`).
- `upgrade` — `apps/backend/alembic/versions/051_mode_gratuit.py:39` — trois create_table, deux index uniques (slug, lane+date), seed.
- `downgrade` — `apps/backend/alembic/versions/051_mode_gratuit.py:115` — drops inverses.

### apps/backend/alembic/versions/052_lane_zai_secours.py
Lu intégralement : oui (72/72 lignes) · sha256: 56f876c2074a · date: 2026-08-25

Ajoute la lane de secours `zai-alt` (« GLM · Z.ai (secours) », modèle `glm-4.5-flash`, mêmes caps, position 10) : quand le primaire répond 429/surcharge, le routeur pose un cooldown et les tours suivants partent sur le secours. La clé vient des mêmes settings (`cle_lane` résout tout slug `zai*`) ; seule `model` distingue les deux lanes (`apps/backend/alembic/versions/052_lane_zai_secours.py:8`).
- `upgrade` — `apps/backend/alembic/versions/052_lane_zai_secours.py:44` — **idempotent** : SELECT préalable sur le slug, retour sans insertion si présent (`apps/backend/alembic/versions/052_lane_zai_secours.py:46`).
- `downgrade` — `apps/backend/alembic/versions/052_lane_zai_secours.py:71` — DELETE par slug.

## Qui écrit quoi (contrat inter-lots)

| Table | Écrite par (lot) | Lue par |
|---|---|---|
| `agent_providers` | services providers (lot 5) | boucle chat (lot 2), endpoints (lot 4) |
| `agent_sessions` / `agent_messages` | boucle + sessions (lot 2) | endpoints sessions/usage (lot 4), front (lot 6) |
| `agent_discovery_quota` | service découverte (lot 5) | endpoint gratuit/découverte (lot 4) |
| `agent_lanes` / `agent_lane_usage` | routeur gratuit (lot 5), migrations seed | endpoint gratuit (lot 4) |
| `agent_gratuit_consents` | endpoint consentement (lot 4) | routeur gratuit (lot 5) |
