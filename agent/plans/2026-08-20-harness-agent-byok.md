# Plan : harness d'agent BYOK dans Philum — chat, workspace ICM, fiches automatisées

> Plan actif — 2026-08-20. Rapport de conception : `agent/research/2026-08-20-harness-agent-philum.md`.
> Vision produit, contraintes du repo, décisions web search et réutilisation : s'y reporter.
> Cible de lecture : Opus 5 (évaluation faisabilité) puis tout agent qui déroule le plan.

---

## Contexte

Créer une **interface de chat LLM BYOK dans l'UI web Philum** : un créateur connecte son
compte IA (OpenAI, Anthropic, DeepSeek, Gemini — ou tout endpoint OpenAI-compatible en
mode custom), et dialogue avec un agent qui a accès à ses fiches (publiques + privées),
à ses sources, à la recherche web, et à un **filesystem de configuration de type ICM**
hébergé où il configure lui-même ses agents (recherche web, création de fiche **100 %
automatisée**).

**Le provider est le cerveau, Philum est les mains et la preuve.** L'inférence tourne
chez le provider (compte utilisateur, payant ou free tier) ; Philum orchestre, exécute
les outils (MCP + web + filesystem), vérifie verbatim et garde la preuve.

## Décisions cadrées (2026-08-20, réponses utilisateur)

| Sujet                    | Décision                                                                                                                                                                                      |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Périmètre MVP            | **Complet + fiches automatisées** : les 4 briques + agents de création de fiche configurables dès le départ                                                                                   |
| Approbation écritures    | **Hybride** : lecture + écritures réversibles (brouillon, sources, extraits) automatiques ; écritures sensibles (`publish`, `delete`, attestation, archivage) soumises à validation dans l'UI |
| Clés API                 | **Serveur chiffré** (AES-GCM, `master_encryption_key` existante) pour le MVP ; mode navigateur (« confiance zéro ») en itération ultérieure                                                   |
| Web search               | **Choix laissé à l'utilisateur** : grounding natif du provider quand il existe, ou API dédiée Philum (Tavily/Exa/Brave/Serper), ou BYOK recherche (clé de l'utilisateur) en option            |
| Configuration des agents | **UI + fichiers** : une UI simple qui lit/écrit des fichiers de config dans le workspace ICM (cohérence entre les deux mondes)                                                                |
| Providers                | **4 providers de base** (OpenAI, Anthropic, DeepSeek, Gemini) **+ mode custom** (base_url + modèle + clé libres, endpoint OpenAI-compatible)                                                  |

---

## Architecture cible

```
┌──────────────────────────── Philum (cloud) ───────────────────────────┐
│                                                                       │
│  SvelteKit    Panneau chat (SSE)   Réglages providers   Config agents │
│  (Vercel)     Approbation inline   (BYOK)               (UI↔fichiers) │
│      │              │                   │                   │         │
│      ▼              ▼                   ▼                   ▼         │
│  Backend   POST /api/v1/agent/chat  ─▶ AgentEngine (boucle modèle→outil→modèle) │
│  FastAPI   (SSE streaming)                 │  │  │  │                    │
│                                           ▼  ▼  ▼  ▼                     │
│                              ToolRegistry:                               │
│                                • philum_*   → mcp_server/tools*.py       │
│                                • web_search → natif provider | API dédiée│
│                                • fetch_url  → document_text              │
│                                • fs_*       → workspace ICM hébergé      │
│                                • fiche_*    → stages automatisés (Ph.5)  │
│  Tables : agent_providers, workspace_files, agent_sessions, agent_messages │
│  Router BYOK (surface OpenAI-compatible + adapter par provider)          │
└────────┼────────────────────────────────────────────────────────────────┘
         ▼  Appels directs au provider avec la clé de l'utilisateur
```

---

## Séquence des phases et des PRs

Chaque phase = 1 à 2 PRs, mergées et déployées en série (convention
`agent/GIT_WORKFLOW.md` : jamais de push direct sur `main`).

| Phase | Contenu                                                                                          | Dépend de | Poids        |
| ----- | ------------------------------------------------------------------------------------------------ | --------- | ------------ |
| 1     | Providers BYOK (table, service, endpoints, UI réglages)                                          | —         | Backend + UI |
| 2     | Workspace ICM hébergé (table, seed, endpoints, outils fs)                                        | —         | Backend      |
| 3     | Moteur d'agent (boucle, streaming SSE, registre d'outils Philum + web + fs, approbation hybride) | 1, 2      | Backend      |
| 4     | Sessions + UI chat + approbation inline + config agents UI↔fichiers                              | 1, 2, 3   | Backend + UI |
| 5     | Agents de création de fiche 100 % automatisée (orchestrateur ICM, checkpoints)                   | 3, 4      | Backend + UI |

---

## Phase 1 — Providers BYOK

**But** : un créateur peut enregistrer ses comptes IA (jusqu'à N, un défaut), et tester
sa clé. Rien d'autre n'en dépend → livrable seul, testable seul.

### 1.1 Migration — `040_agent_providers.py`

Table `agent_providers` :

| Colonne                    | Type               | Contrainte                                             |
| -------------------------- | ------------------ | ------------------------------------------------------ |
| `id`                       | uuid pk            |                                                        |
| `creator_id`               | uuid fk → users.id | `ondelete=cascade`                                     |
| `provider`                 | str(20)            | `openai \| anthropic \| deepseek \| gemini \| custom`  |
| `display_name`             | str(80)            | défaut = `provider` ; personnalisable pour `custom`    |
| `base_url`                 | str(300)           | requis pour `custom` ; défaut par provider sinon       |
| `model`                    | str(120)           | requis                                                 |
| `api_key_enc`              | text               | **chiffré AES-GCM** via `KeyManager` (jamais en clair) |
| `is_default`               | bool               | un seul défaut par créateur                            |
| `created_at`, `updated_at` | timestamptz        |                                                        |

Unicité : `(creator_id, provider, base_url, model)` pour éviter les doublons.
Retrait partiel : `039_oauth_dcr.py` sert de modèle de migration (voir son style).

### 1.2 Modèle + schémas

- `app/models/agent_provider.py` : SQLAlchemy `AgentProvider` (style `user.py`).
- `app/schemas/agent_provider.py` :
  - `AgentProviderCreate` : `provider, display_name?, base_url?, model, api_key`
  - `AgentProviderUpdate` : champs optionnels ; `api_key` remplacée si fournie
  - `AgentProviderRead` : **sans `api_key`** — renvoie `api_key_masked` (`sk-…1234`)
  - validation : si `provider == custom`, `base_url` obligatoire et valide
    (http/https, `url_safety.py` existant pour l'assainissement)

### 1.3 Service — `app/services/agent_providers.py`

- `lister(creator)`, `creer(creator, payload)`, `mettre_a_jour(creator, id, payload)`,
  `supprimer(creator, id)`, `resoudre_defaut(creator)`.
- Chiffrement : `KeyManager(settings.master_encryption_key)` (pattern
  `app/services/auth.py` ligne 58) — encrypter `api_key`, décrypter à la lecture
  **jamais en clair hors service**.
- **Résolution de l'endpoint chat** (reprendre la logique `url_chat()` de
  `app/services/llm.py` ligne 49) : un chemin dans `base_url` → suffixe
  `/chat/completions` ; racine nue → `/v1/chat/completions`.
- **Adapters par provider** (inspiré du `llm-pi-ai` de dsh) : la surface par défaut
  est OpenAI-compatible (`/v1/chat/completions`), ce que DeepSeek, Gemini
  (`/v1beta/openai`) et OpenAI exposent nativement. Anthropic expose une surface
  OpenAI-compatible ; un adapter dédié (`app/services/agent_providers_anthropic.py`)
  traduit vers `/v1/messages` si le test de compat échoue. Les différences de champ
  (`max_tokens` vs `max_completion_tokens`, rôle système) sont gérées dans un dict de
  transform par provider, jamais dans le moteur.
- **Test de clé** : `tester(provider_id)` — un appel minimal (1 token, température 0,
  prompt « ping ») ; retourne `{ok, http_status, model_resolved, message_actionnable}`
  (clé invalide, quota épuisé, modèle inconnu → message distinct).

### 1.4 Endpoints — `app/api/v1/endpoints/agent_providers.py`

| Méthode | Route                        | Fonction                          |
| ------- | ---------------------------- | --------------------------------- |
| GET     | `/agent/providers`           | lister les miens (masqué)         |
| POST    | `/agent/providers`           | créer                             |
| PATCH   | `/agent/providers/{id}`      | mettre à jour (dont `is_default`) |
| DELETE  | `/agent/providers/{id}`      | supprimer                         |
| POST    | `/agent/providers/{id}/test` | tester la clé                     |

Auth : dépendance créateur existante (pattern `users.py`). Rate limit : `rate_limit.py`.
Router : enregistrer dans `app/api/v1/router.py`.

### 1.5 UI — réglages providers

- Route `src/routes/dashboard/agents/` : liste des providers enregistrés
  (badge modèle, `api_key_masked`, bouton « tester », bouton « défaut »).
- Route `src/routes/dashboard/agents/new` : formulaire (provider → champs adaptés,
  mode custom = base_url libre), test de clé en live avant enregistrement.
- Composants `src/lib/components/agents/ProviderForm.svelte`,
  `ProviderCard.svelte`.

### 1.6 Tests

- `tests/unit/test_agent_providers.py` : chiffrement/déchiffrement, masquage de clé,
  résolution d'endpoint (racine nue vs chemin), validation custom.
- `tests/integration/test_agent_providers_api.py` : CRUD scopé par créateur (A ne voit
  pas les providers de B), `extra="forbid"` sur les payloads (leçon PR #407), test de
  clé avec un fake transport httpx (pas d'appel réseau dans les tests).

---

## Phase 2 — Workspace ICM hébergé

**But** : chaque créateur a un filesystem de configuration type ICM (celui de
`workspaces/createur-de-fiches/`), persisté en base, avec des outils agent
`read_file` / `write_file` / `list_dir` et des endpoints REST.

### 2.1 Migration — `041_workspace_files.py`

Table `workspace_files` :

| Colonne      | Type               | Contrainte                                 |
| ------------ | ------------------ | ------------------------------------------ |
| `id`         | uuid pk            |                                            |
| `creator_id` | uuid fk → users.id | cascade                                    |
| `path`       | str(500)           | **normalisé** ; `UNIQUE(creator_id, path)` |
| `content`    | text               |                                            |
| `sha256`     | str(64)            | hash du contenu (traçabilité)              |
| `updated_at` | timestamptz        |                                            |

### 2.2 Service — `app/services/agent_workspace.py`

- **Normalisation de chemin** (leçon sécurité) : résoudre `..`, refuser les chemins
  absolus et toute remontée hors racine ; racines autorisées : `shared/`, `stages/`,
  `_core/`, `runs/`, `setup/`, `AGENTS.md`, `CONTEXT.md`. Réutiliser
  `app/core/url_safety.py` (logique d'assainissement).
- `lire(creator, path)`, `ecrire(creator, path, content)` (recalcule `sha256`),
  `lister(creator, prefix)` (arborescence), `supprimer(creator, path)`.
- **Seed par créateur** : à la création d'un provider ou à l'inscription, copier un
  snapshot statique du template ICM. Snapshot = copie gelée des fichiers actuels de
  `workspaces/createur-de-fiches/` (AGENTS.md, CONTEXT.md, `shared/*.md`,
  `stages/*/CONTEXT.md`, `_core/templates/*`, `_core/audit/audit_fiche.py`) dans
  `apps/backend/app/agent_workspace_seed/` (un coup de script
  `app/scripts/build_workspace_seed.py` qui gèle le snapshot ; le workspace de dev
  reste la source d'édition). `seed(creator)` insère les fichiers manquants
  (idempotent, ne **jamais** écraser un fichier que l'utilisateur a modifié).

### 2.3 Endpoints

| Méthode | Route                          | Fonction                        |
| ------- | ------------------------------ | ------------------------------- |
| GET     | `/agent/workspace/tree`        | arborescence (prefix optionnel) |
| GET     | `/agent/workspace/file?path=…` | contenu                         |
| PUT     | `/agent/workspace/file?path=…` | écrire (corps = contenu)        |
| DELETE  | `/agent/workspace/file?path=…` | supprimer                       |
| POST    | `/agent/workspace/seed`        | re-seed idempotent              |

Auth créateur + rate limit. Même fichier endpoints `agent_workspace.py`, enregistré au
router.

### 2.4 Outils agent (registre, consommés en Phase 3)

Définis dans `app/agent_tools/workspace.py` (schéma tool dsh-like :
`name, description, parameters, output, execute`) :

- `fs_read(path)` — lit un fichier du workspace
- `fs_write(path, content)` — écrit (avec `sha256` retourné)
- `fs_list(path)` — liste le dossier

Description des outils = docstring qui oriente l'agent vers les règles du workspace
(« lis `shared/principes-editoriaux.md` avant d'écrire »), même logique que le MCP.

### 2.5 Tests

- `tests/unit/test_agent_workspace.py` : normalisation de chemin (tentatives `..`,
  absolus, encodage), seed idempotent qui préserve les fichiers modifiés, sha256.
- `tests/integration/test_agent_workspace_api.py` : isolation par créateur.

---

## Phase 3 — Moteur d'agent

**But** : la boucle modèle → outil → modèle, en streaming SSE, avec les outils Philum
(MCP), web search, et filesystem ICM ; approbation hybride.

### 3.1 Service — `app/services/agent.py`

- **Boucle** (concept dsh `llm-pi-ai` + Cordis, réimplémenté en Python) :
  1. construire les messages (historique + turn courant)
  2. appeler le provider du créateur (router BYOK, Phase 1)
  3. si le modèle demande un outil → exécuter via le registre → ajouter le résultat
     aux messages → retourner en 2 (avec garde-fous)
  4. sinon → streamer la réponse finale
- **Garde-fous** : `MAX_TOURS = 24`, `MAX_TURN_TOKENS = 8192`, timeout par tour
  (45 s, constantes du service), budget temps global ; au dépassement : message
  terminal explicite, pas de boucle silencieuse.
- **Streaming SSE** : route `POST /api/v1/agent/chat` renvoie un flux d'événements :
  `message_delta` (tokens), `tool_call` (outil + args), `tool_result`,
  `approval_request`, `approval_resolved`, `done`, `error`. Format :
  `data: {"type": "...", "payload": {...}}\n\n`.
- **Écritures réversibles** (`create_card`, `add_source`, `add_excerpt`,
  `update_card`, `update_source`, `update_source`…) : exécutées **directement**
  (elles sont corrigeables). **Écritures sensibles** (`publish_card`, `delete_card`,
  `delete_source`, `create_content_attestation`, `archive_sources`, `verify_excerpts`
  avec `provided_text`) : l'agent émet `approval_request` et **suspend** la boucle ;
  l'utilisateur répond dans l'UI, le backend reprend. Liste des sensibles dans un
  ensemble constant (`SENSITIVE_TOOLS`), réutilisée par le front.
- **Compat** « le LLM propose, la crypto dispose » : toute écriture passe par les
  mêmes services que le REST/MCP (invariants, `suggested_by_ai`, `annotated_by_ai`) ;
  un agent ne peut pas écrire sur une fiche d'un autre créateur (auth par créateur).

### 3.2 Registre d'outils — `app/agent_tools/`

Structure : `registry.py` (déclaration + `execute(name, args, ctx)`), `ctx` porte
`creator`, `db`, `approuver` (callback). Outils :

- **`philum.py`** — wrappe les fonctions de `app/mcp_server/tools.py` +
  `tools_write.py` (elles délèguent déjà aux services REST, mêmes invariants).
  Le `creator` de l'agent devient l'utilisateur des appels. Tools exposés :
  `search_cards`, `get_card`, `get_source`, `find_cards_citing`, `create_card`,
  `add_source`, `add_excerpt`, `set_content_text`, `update_card`, `update_source`,
  `list_my_cards`, `list_sources`, `search_my_excerpts`, `verify_excerpts` (sensible),
  `publish_card` (sensible), `delete_card` (sensible), `delete_source` (sensible),
  `suggest_excerpts`, `annotate_excerpt`, `parse_biblio`, `add_sources_batch`,
  `get_url_metadata`, `import_from_content_url`.
- **`web.py`** — `web_search(query)` et `fetch_url(url)` :
  - `web_search` : **résolution à l'exécution** — si le provider courant expose le
    grounding natif (Gemini), l'utiliser ; sinon utiliser l'API dédiée configurée
    (env `agent_web_search_provider` + `agent_web_search_api_key`, type
    tavily/exa/brave/serper) ; si une clé BYOK recherche est enregistrée pour le
    créateur, l'utiliser en priorité. Retourne des **URLs brutes** + titres +
    snippets (jamais une synthèse).
  - `fetch_url` : réutilise `app/services/document_text.py` (anti anti-bot existant).
- **`workspace.py`** — Phase 2 (§2.4).
- **`fiche.py`** — Phase 5 (stub en Phase 3 : `fiche_state(slug)`, lancer les
  orchestrations).

### 3.3 Config

`app/core/config.py` — ajouter :
`agent_max_tours: int = 24`, `agent_max_turn_tokens: int = 8192`,
`agent_web_search_provider: str = ""` (tavily/exa/brave/serper),
`agent_web_search_api_key: str = ""`.

### 3.4 Tests

- `tests/unit/test_agent_loop.py` : boucle avec un fake provider (httpx MockTransport) —
  modèle qui demande 2 outils puis répond ; garde-fous (trop de tours, timeout).
- `tests/unit/test_agent_tools.py` : chaque outil, wrapper avec user mocké ;
  **l'agent ne voit jamais le workspace ni les fiches d'un autre créateur**.
- `tests/integration/test_agent_chat.py` : route SSE (rendu complet du flux),
  suspension/reprise sur `approval_request`.

---

## Phase 4 — Sessions, UI chat, config agents UI↔fichiers

### 4.1 Migration — `042_agent_sessions.py`

Tables :

- `agent_sessions` : `id, creator_id, title, provider_id (nullable), created_at,
updated_at, last_message_at`.
- `agent_messages` : `id, session_id, role (user|assistant|tool), content, tool_calls
(jsonb), created_at` — **append-only** (jamais de UPDATE).

### 4.2 Endpoints

| Méthode | Route                           | Fonction                                                               |
| ------- | ------------------------------- | ---------------------------------------------------------------------- |
| GET     | `/agent/sessions`               | lister les miennes (titre, date)                                       |
| POST    | `/agent/sessions`               | créer (title, provider_id)                                             |
| GET     | `/agent/sessions/{id}/messages` | historique (read-only)                                                 |
| POST    | `/agent/chat`                   | nouveau message + streaming SSE (créer la session si absente)          |
| POST    | `/agent/approve`                | résoudre une `approval_request` (`{session_id, request_id, approved}`) |
| DELETE  | `/agent/sessions/{id}`          | supprimer (logique)                                                    |

### 4.3 UI

- **Route `src/routes/dashboard/chat/`** + `[id]` : panneau de chat (SSE via
  `EventSource`/fetch streaming), bulles agent/utilisateur, cartes `tool_call`
  (outil, args), boutons d'approbation inline pour les actions sensibles
  (Verrouiller les réversibles en automatiq… : le front affiche une carte
  « L'agent souhaite publier la fiche X » avec **Accepter / Refuser**).
- **Route `src/routes/dashboard/agents/`** : réglages providers (Phase 1) **+
  config des agents** — liste des agents configurables (recherche web, création de
  fiche) ; formulaire qui **lit/écrit des fichiers de config dans le workspace ICM**
  (convention : `agents/<slug>.yaml` avec `name, model, instructions, tools,
icm_stages`). L'UI est un éditeur de ces fichiers (cohérence UI ↔ fichiers,
  décision actée).
- Composants : `src/lib/components/chat/` (ChatPanel, ChatMessage, ToolCard,
  ApprovalCard), `src/lib/components/agents/AgentForm.svelte`.

### 4.4 Tests

- Backend : CRUD sessions, isolation par créateur, endpoint approve (refus → l'outil
  ne s'exécute pas).
- Front : tests vitest du composant SSE (mock du flux) et du rendu ApprovalCard.

---

## Phase 5 — Agents de création de fiche 100 % automatisée

**But** : un agent configurable (Phase 4) qui, recevant un `content_url`, déroule les
7 étages ICM dans le workspace et produit une fiche publiée, avec checkpoints humains.

### 5.1 Config d'un agent de fiche

Fichier `agents/creation-fiche.yaml` dans le workspace (éditable via l'UI) :

```yaml
name: creation-fiche
model: default # provider défaut du créateur
instructions: stages/01-brief/CONTEXT.md # pointeur vers les règles ICM
icm_stages:
  - id: 01-brief
    output: runs/<slug>/00-brief.md
  - id: 02-sources-collectees
    output: runs/<slug>/01-sources.md
  # … 03-annotations, 04-extraits, 05-connexions, 06-relecture, 07-publication
checkpoints:
  - stage: 07-publication # l'approbation humaine est requise ici
```

### 5.2 Orchestrateur — `app/services/agent_fiche.py`

- `lancer(session_id, content_url)` : crée `runs/<slug>/`, lit les `CONTEXT.md` des
  étages (workspace), construit le brief (template `_core/templates/brief.md`),
  puis pour chaque étage : **lire la config du workspace → exécuter les outils
  Philum (create_card, import_from_content_url, add_source, add_excerpt,
  verify_excerpts…) → écrire les outputs dans le workspace → audit léger**
  (`_core/audit/audit_fiche.py` adapté en service).
- **Checkpoints** : aux étages marqués (publication, attestation), l'orchestrateur
  émet `approval_request` (réutilise Phase 3) et attend.
- **Traçabilité** : chaque étape écrit son output dans le workspace + les messages
  dans `agent_messages` (append-only) ; l'audit produit des alertes non bloquantes
  (décision : alertes, pas de blocage — règle du workspace).

### 5.3 UI

- Bouton « Créer une fiche » dans le chat / dashboard → saisie de `content_url`,
  lancement, suivi des étages (progression), approbation inline au checkpoint.

### 5.4 Tests

- `tests/unit/test_agent_fiche.py` : orchestration avec les services mockés —
  séquence d'étages, écriture des outputs, checkpoints respectés.
- `tests/integration/test_agent_fiche_e2e.py` : fiche de bout en bout sur un contenu
  factice (provider fake), vérifie les invariants (extraits vérifiés avant
  publication, audit tracé dans le verdict).

---

## Sécurité (transversale)

- **Clés API** : chiffrées AES-GCM avec `master_encryption_key`, décryptées seulement
  dans le service providers, **jamais loggées ni renvoyées** (masquage `sk-…1234`).
- **Filesystem** : normalisation de chemin stricte (pas de `..`, pas d'absolu, racines
  fermées) ; `extra="forbid"` sur les payloads (leçon PR #407).
- **Isolation multi-tenant** : tout (providers, workspace, sessions, écritures Philum)
  scopé par `creator_id` ; l'agent ne voit jamais le contenu d'un autre créateur.
- **Pas d'exécution de code** : aucun outil « bash / exécuter du code » dans le
  registre (surface d'attaque interdite).
- **Approbation hybride** : liste fermée `SENSITIVE_TOOLS` ; toute action sensible
  suspends et attend validation. Un `publish_card` n'a jamais lieu sans accord.
- **Principe LLM propose / crypto dispose** : toute sortie entrant dans une fiche
  passe par les invariants existants (extraits vérifiés verbatim, verdicts,
  attestation signée par le créateur, jamais par l'agent).

---

## Risques et parades (rappel du rapport §8)

| Risque                                  | Parade                                                                                   |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| Vol de la VM → clés exposées            | MVP : chiffrement + rotation ; itération suivante : mode navigateur (« confiance zéro ») |
| Provider natif web search = boîte noire | Retourne des URLs brutes ; la vérification passe par les oracles Philum                  |
| Boucle d'agent infinie / coût           | Garde-fous (tours, tokens, temps) ; quota provider = compte utilisateur                  |
| Developer preview dsh                   | Aucune dépendance à dsh en dur ; concepts repris, code Philum                            |
| Contexte VM e2-micro                    | Moteur in-process asyncio partagé, pas de process par session                            |

---

## Ordre de déploiement et vérification

1. Phase 1 → vérifier en dev : enregistrer un provider Gemini, tester la clé, voir le
   masquage dans l'UI.
2. Phase 2 → vérifier : seed du workspace à l'inscription, écrire/lire un fichier via
   l'endpoint, tenter `..` (refusé).
3. Phase 3 → vérifier : un chat qui appelle `search_cards` puis répond (fake provider
   en test ; vrai provider en dev), approbation suspend/répond.
4. Phase 4 → vérifier : historique de session persistant, UI chat avec cartes d'outils
   et approbation inline, édition d'un agent via l'UI = fichier écrit dans le workspace.
5. Phase 5 → vérifier : fiche factice de bout en bout, checkpoint de publication,
   audit tracé, fiche visible sur le web après approbation.

Chaque phase livrée = PR mergée + déploiement (VM backend, Vercel front) +
retour dans `STATE.md` (contrat de continuité du repo).
