# 2026-08-20 — Rapport : intégrer un harness d'agent dans Philum

> **Objet** : explorer le champ des possibles pour intégrer un harness d'agent (type
> `deepseek-ai/deepseek-harness`) dans Philum, afin que les créateurs utilisent leurs
> **propres comptes IA** (OpenAI, Anthropic, DeepSeek, Gemini — payants ou free tiers)
> **depuis l'interface Philum**. Ce rapport est destiné à être évalué par Opus 5 pour
> pertinence et faisabilité. Tout ce qui est cité a été vérifié dans le repo au 2026-08-20.
>
> **Clarifié le 2026-08-20 après échanges** : vision produit précisée (§1), place des
> capacités natives du provider (§1.1), décision web search (Firecrawl écarté, §3.5,
> §7).

---

## 1. Contexte et objectif

**Vision produit (clarifiée 2026-08-20, après échanges)** : créer **une interface de chat
LLM BYOK dans l'UI web Philum** qui permet aux créateurs :

1. d'utiliser **leur LLM préféré directement dans Philum** (OpenAI, Anthropic, DeepSeek,
   Gemini — payant ou free tier, via leur propre compte) ;
2. avec **accès au contenu public Philum** (fiches, sources, graphe de citations) **et au
   contenu privé de l'utilisateur** (ses brouillons, ses fiches non publiées, ses
   extraits) ;
3. en **configurant eux-mêmes leurs propres agents** : agents de recherche web, agents de
   création de fiche **100 % automatisée**, via un filesystem de configuration de type
   ICM ;
4. et en bénéficiant des **capacités natives du provider** (web search, skills) quand le
   provider les expose dans son API.

L'accroche publique de Philum promet déjà : *« interrogez une IA sur ces sources et rien
d'autre »* (STATE.md, session 2026-08-14/15, PR #383). La fonctionnalité BYOK concrétise
et dépasse cette promesse : un agent conversationnel complet, dans l'interface Philum,
qui tourne sur le compte IA de l'utilisateur.

### 1.1 Ce que le provider apporte, et ce que Philum doit couvrir

Le **web search et les skills du provider suivent le compte de l'utilisateur** quand le
provider les expose via API (Gemini : grounding Google Search natif ; OpenAI/Anthropic :
outil `web_search`). Mais ce n'est ni universel, ni suffisant :

| Réserve | Conséquence pour l'architecture |
|---|---|
| **Pas universel** — DeepSeek n'a pas de web search natif ; pas tous les providers exposent leurs « skills » via API (certains ne vivent que dans l'UI du provider). | Philum ne peut pas dépendre du web search natif : il faut un web search **Philum** (API dédiée) uniforme, en plus du natif quand il existe. |
| **Pas toujours dans le free tier** — le web search natif est souvent réservé aux plans payants (Anthropic/OpenAI). | Sur un compte free tier, le web search Philum reste disponible. |
| **Boîte noire** — le natif renvoie une réponse synthétisée, pas les URLs brutes vérifiables. | Pour l'exactitude Philum, la **découverte** d'URLs peut être native, la **vérification** passe toujours par les oracles + pipeline maison. |

**Principe retenu** : *« le provider = le cerveau (le LLM que l'utilisateur choisit),
Philum = les mains et la preuve (outils MCP + oracles + vérification verbatim) »*. Le
web search natif du provider est un bonus quand il existe ; les agents de création de
fiche reposent sur les outils Philum, qui garantissent le niveau d'exactitude — quel que
soit le LLM connecté.

### 1.2 Décisions déjà actées avec l'utilisateur (2026-08-20)

1. **L'inférence tourne chez le provider** (compte de l'utilisateur, payant ou free
   tier). Philum ne paie pas les tokens de l'utilisateur.
2. **L'agent n'est pas cantonné aux outils Philum** : il veut aussi du web search et du
   filesystem.
3. **Le « filesystem » = un filesystem de configuration d'agents de type ICM** : le
   workspace de création de fiches tel qu'il existe déjà dans
   `workspaces/createur-de-fiches/` (structure `shared/`, `stages/`, `_core/`, `runs/`),
   hébergé par créateur dans Philum. C'est là que l'utilisateur configure ses agents
   (recherche web, fiche automatisée) et où l'agent lit/écrit sa config et ses règles.
4. Conséquence : **architecture 100 % cloud** — inference chez le provider, orchestration
   chez Philum, fichiers et recherche web chez Philum. Pas de composant local dans un
   premier temps.

---

## 2. Ce qu'est `deepseek-harness` (dsh) et ce qu'il apporte

Repo : `https://github.com/deepseek-ai/deepseek-harness` (MIT, developer preview).
Harness d'agent construit sur Cordis : *« everything is a plugin »*.

### 2.1 Capacités pertinentes

| Capacité | Détail vérifié | Pertinence Philum |
|---|---|---|
| **Multi-provider LLM** | Provider natif DeepSeek ; OpenAI et Anthropic au catalogue ; **custom provider OpenAI-compatible** (Gemini, tout endpoint) ; auth native Bedrock/Vertex/Azure/Codex. | C'est exactement le besoin BYOK : un routeur vers OpenAI, Anthropic, DeepSeek, Gemini. |
| **Gestion des compat provider** | Module `llm-pi-ai` : `max_tokens` vs `max_completion_tokens`, `supportsDeveloperRole`, formats de « thinking », catalogues de modèles, endpoints custom, fallbacks. | Valeur réutilisable en inspiration : ce sont les pièges exacts que Philum contourne déjà dans `app/services/llm.py`. |
| **Clés write-only** | Stockées dans `$DSH_HOME/.credentials.yaml`, jamais renvoyées à l'UI. | Modèle de référence pour la sécurité des clés utilisateur. |
| **Registre d'outils** | `ctx.tools.register(defineTool({name, description, parameters, output, execute}))`. | Equivalent Philum : le serveur MCP existant. |
| **Journal de session** | Log de session append-only. | Réutilisable comme modèle pour l'historique de conversation. |
| **Boucle d'agent** | Agent loop Cordis avec politiques d'approbation (« the Web UI asks before operations that require approval »). | C'est le moteur à construire. |
| **UI web locale** | `npx @deepseek-ai/dsh web` → UI sur `127.0.0.1:3080`, Settings → Models, choix de workspace, approbation. | Local-first, pas multi-tenant web : à ré-imaginer dans l'UI Philum. |

### 2.2 Ce qui ne colle pas tel quel

- **Stack** : dsh est TypeScript/Node (pnpm). Le backend Philum est Python/FastAPI.
  Impossibilité d'embarquer dsh in-process. → on s'inspire, on ne dépend pas.
- **Orienté local-first et filesystem** : les workspaces dsh sont des répertoires de la
  machine. Une web app hébergée n'a pas de filesystem local.
- **Developer preview** : compatibilité cassante annoncée (« compatibility-breaking
  changes »), ~13 k commits. → ne pas prendre de dépendance vivante non pinnée.
- **Outils par défaut inadaptés** : bash / édition de fichiers arbitraire = surface
  de sécurité inacceptable dans une web app multi-tenant.

**Conclusion §2** : la valeur à prélever est **architecturale et conceptuelle** (routeur
multi-provider, registre d'outils, journal, approbation), pas le code.

---

## 3. Contraintes constatées dans le code Philum

### 3.1 Architecture d'hébergement

- Backend FastAPI (`apps/backend/app/`) sur VM GCP e2-micro (always-free), Postgres
  Supabase free, front SvelteKit sur Vercel (`apps/frontend/`), extension MV3
  (`apps/extension/`). Source : STATE.md « État production vérifié (2026-07-21) » et
  ADR-028.
- Le backend est **multi-tenant** : identité par créateur (Google OAuth), ressources
  scopées par `creator_id`. Un agent par créateur hérité de ce modèle.

### 3.2 La couche LLM centrale existe déjà

- `infra/litellm/config.yaml` + `app/services/llm.py` : **un seul point de contact LLM**
  (proxy LiteLLM self-hosted), routage par **alias de tâche** (`metadata-extract`,
  `web-search`, `wayback-match`, `graph-build`, `fact-signals`, `biblio-parse`,
  `excerpt-suggest`) avec cascades de fallback. Politique de sensibilité par tâche
  (EU/US uniquement pour les données pré-publication).
- `.docs/17-llm-strategy.md` pose les principes : pas de SDK provider dans le backend,
  **pas d'appel LLM synchrone dans une route HTTP**, le LLM propose / la crypto dispose.
- Piège connu (PR #392) : le quota Gemini se compte par modèle/jour, fallbacks ordonnés
  (`llm_direct_model_fallbacks`) nécessaires.
- **Le BYOK est orthogonal** : un chemin *par utilisateur* (surface OpenAI-compatible)
  à côté du chemin *central* (proxy LiteLLM). La couche centrale reste pour les
  suggestions internes (extraction, annotation, excerpt-suggest).

### 3.3 Le serveur MCP est déjà un registre d'outils

`apps/backend/app/mcp_server/server.py` (FastMCP) expose **30 outils** :
- Lecture : `search_cards`, `get_card`, `get_source`, `find_cards_citing`, `whoami`.
- Écriture : `create_card`, `add_source`, `add_excerpt`, `set_content_text`,
  `publish_card`, `update_card`, `update_source`, `delete_source`, `delete_excerpt`,
  `verify_excerpts`, `list_connections`, `confirm_connection`, `remove_connection`,
  `list_my_cards`, `list_sources`, `search_my_excerpts`, `delete_card`, `restore_card`,
  `archive_sources`, `suggest_excerpts`, `annotate_excerpt`, `chunk_text`,
  `get_youtube_transcript`, `get_url_metadata`, `import_from_content_url`,
  `create_content_attestation`, `get_attestation`, `verify_attestation`,
  `list_incoming_citations`, `add_sources_batch`, `parse_biblio`…
- Auth : token MCP via `POST /api/v1/auth/mcp-token`, `Authorization: Bearer`
  (PRs #444/#445). Tout est scopé par créateur.
- **Tous ces outils délèguent aux services REST** → réutilisables directement comme
  outils de l'agent (mêmes invariants, mêmes tests).

### 3.4 Le workspace ICM existe déjà

`workspaces/createur-de-fiches/` est la méthode 7 étapes qui a produit la fiche
Stellaris (déjà publiée) :

```
createur-de-fiches/
  AGENTS.md, CLAUDE.md, CONTEXT.md        # règles + contexte du processus
  shared/                                 # principes transverses
    garde-fous.md  pieges-vecus.md  principes-editoriaux.md
    voix-createur.md  philum-mcp.md
  stages/                                 # les 7 étapes du pipeline
    01-brief/ 02-sources-collectees/ 03-annotations/ 04-extraits/
    05-connexions/ 06-relecture/ 07-publication/
    (chacun : CONTEXT.md + output/)
  _core/
    audit/audit_fiche.py                 # audit scripté (alertes, non bloquant)
    templates/brief.md source.md extrait.md
  runs/
    stellaris-stellarator-centrale-fusion/…  # un dossier par fiche produite
```

Ce workspace incarne les règles éditoriales que l'utilisateur a gravées le 2026-08-19
(titre exact du contenu, dates tracées, alertes non bloquantes). C'est **ce qu'un agent
par créateur doit pouvoir lire et écrire** : c'est la « config de l'agent » au sens ICM.

### 3.5 Web search

- **Firecrawl n'est intégré nulle part** : `.firecrawl/` ne contient que des JSON de test
  (résultats de recherche Zotero/paywalls), gitignorés comme cache local. L'alias
  `web-search` existe dans `infra/litellm/config.yaml` (grounding Gemini natif) mais
  n'est appelé par aucun code du backend.
- L'exigence d'exactitude de Philum repose sur des **oracles structurés** par source de
  vérité (`app/extractors/` : Crossref, OpenAlex/Unpaywall, retraction, NCBI BioC,
  Semantic Scholar, Wikipedia, YouTube) + scraping direct durci (`_html_scrape` :
  détection de murs anti-bot, retry, verdicts `unreadable`) — principe « API > scraping »
  de `.docs/17-llm-strategy.md`.
- Pour un outil de web search de l'agent, la recommandation de `.docs/17-llm-strategy.md`
  §3.2 tient : **API de recherche dédiée (Tavily/Exa/Brave/Serper) qui retourne des URLs
  brutes vérifiables + LLM synthétiseur**, ou grounding natif du provider choisi. Pas de
  dépendance Firecrawl : il n'apporterait rien au niveau d'exactitude exigé (métadonnées
  → oracles Crossref/OpenAlex, texte de page → pipeline maison, découverte d'URLs →
  API dédiée).

### 3.6 Contraintes de ressources

- VM e2-micro (1 vCPU, ~1-2 GB RAM) : aucun agent tournant en process par session
  utilisateur, ni serveur Node par utilisateur. Le moteur d'agent doit être **léger,
  in-process FastAPI, asyncio**, partagé.

---

## 4. Architecture proposée (cible)

### 4.1 Vue d'ensemble

```
            ┌──────────────────────────── Philum (cloud) ───────────────────────────┐
            │                                                                       │
  SvelteKit │  Panneau de chat agent        Page réglages providers (BYOK)          │
  (Vercel)  │  Historique des sessions                                                │
            │        │                                     │                          │
            │        ▼                                     ▼                          │
  Backend   │  POST /api/v1/agent/chat  ──▶  AgentEngine (boucle modèle→outil→modèle)│
  FastAPI   │        │  (streaming)              │  │  │  │                            │
            │        ▼                        ┌──┴──┴──┴──┐                           │
            │  Service agent                 │  Outils    │  → Outils Philum (MCP)    │
            │  (app/services/agent.py)       │  registre  │  → Web search (API dédiée) │
            │        │  session log          │            │  → Filesystem ICM hébergé│
            │        ▼                       └────┬───────┘                           │
            │  agent_sessions (append-only)      │                                    │
            │  workspace_files (par créateur)    │                                    │
            │        │                            │                                    │
            │        ▼                            ▼                                    │
            │  Router BYOK : OpenAI / Anthropic / DeepSeek / Gemini (OpenAI-compatible)│
            └────────┼────────────────────────────────────────────────────────────────┘
                     ▼
        Appels directs au provider avec la clé de l'utilisateur
        (l'inférence tourne chez le provider, sur le compte de l'utilisateur)
```

### 4.2 Brique 1 — Providers BYOK

- Table `agent_providers` : `(id, creator_id, provider, base_url, model, api_key_enc,
  is_default, created_at, updated_at)`. Clé chiffrée (le repo a déjà `app/crypto/` et une
  `master_encryption_key` — cf. STATE.md infra).
- Service `app/services/agent_providers.py` : CRUD par créateur + **résolution de
  l'endpoint chat** (surface OpenAI-compatible, même logique que `url_chat()` dans
  `llm.py`).
- Client : appels **directs** au provider choisi (httpx / AsyncOpenAI) avec la clé de
  l'utilisateur — jamais via le proxy central (qui, lui, reste pour les suggestions
  internes de Philum).
- Endpoints REST + UI de réglages (ajout/suppression de compte, modèle, test de clé).

### 4.3 Brique 2 — Workspace de configuration ICM hébergé

- Table `workspace_files` : `(creator_id, path, content, sha, updated_at)`. Paths
  normalisés (`shared/…`, `stages/…`, `_core/…`, `runs/<slug>/…`), interdiction de
  remonter hors du workspace (pas de `..`, pas de chemin absolu).
- **Seed par créateur** : copie du template ICM existant (`shared/`,
  `stages/*/CONTEXT.md`, `_core/templates/`, `_core/audit/audit_fiche.py`).
- Outils agent : `read_file(path)`, `write_file(path, content)`, `list_dir(path)`,
  versionnés (sha256 + horodatage) pour traçabilité.
- C'est le « filesystem de configuration d'agents type ICM » demandé.

### 4.4 Brique 3 — Moteur d'agent

- `app/services/agent.py` : boucle asynchrone **modèle → outil → modèle**, streaming
  SSE, garde-fous (nombre max de tours, temps max, tokens max). Modèle calqué sur le
  concept dsh (`llm-pi-ai` + registre d'outils) mais en Python.
- **Registre d'outils** :
  - Outils Philum : réutiliser `mcp_server/tools.py` et `tools_write.py` (ils délèguent
    aux mêmes services que le REST, mêmes invariants, auth par créateur).
  - Web search : API de recherche dédiée (Tavily/Exa/Brave/Serper) qui rend des URLs
    brutes traçables, ou grounding natif du provider choisi + outil `fetch_url` (le
    pipeline document_text existant).
  - Filesystem ICM : les outils de 4.3.
- **Approbation** : pattern dsh — l'agent propose, l'utilisateur valide les actions
  d'écriture (publish, delete) via l'UI. Cohérent avec le principe Philum « le LLM
  propose, la crypto dispose » (ADR-019, `.docs/17-llm-strategy.md` §1.5).
- **Jamais d'appel synchrone dans une route HTTP** (principe `.docs/17-llm-strategy.md`
  §4.4) : job asyncio + statut, ou streaming SSE accepté si borné. À trancher.
- L'agent parle à la fois au workspace ICM (config + règles, genre
  `shared/principes-editoriaux.md`) et aux fiches Philum (MCP) : les deux mondes se
  rejoignent dans une boucle.

### 4.5 Brique 4 — Sessions et UI

- Table `agent_sessions` : log append-only (rôle, message, tool_call, résultat),
  reprenable (reprise de conversation), scopé par créateur.
- UI SvelteKit : panneau de chat (composant type `ConversationNodeDefinition`),
  page de réglages providers, historique des sessions.

---

## 5. Ce qui existe déjà et se réutilise tel quel

| Besoin | Existant Philum |
|---|---|
| Outils de manipulation de fiches/sources/extraits | `apps/backend/app/mcp_server/tools.py` + `tools_write.py` (30 outils, auth créateur) |
| Point de contact LLM interne | `app/services/llm.py` + proxy LiteLLM (à ne PAS utiliser pour le BYOK) |
| Chiffrement | `app/crypto/` + `master_encryption_key` |
| Identité multi-tenant | JWT créateur + `POST /api/v1/auth/mcp-token` |
| Extraction de texte de pages | `app/services/document_text.py` (anti anti-bot : NCBI API, retry 429, détection de murs, PRs #401-#403, #411) |
| Recherche par le sens / plein texte | `excerpt_search.py`, `card_search.py` (pgvector + unaccent) |
| Template de workspace ICM | `workspaces/createur-de-fiches/` (shared/, stages/, _core/, runs/) |
| Audit scripté non bloquant | `_core/audit/audit_fiche.py` (titre exact, dates, alertes) |

---

## 6. Champ des possibles — variantes et périmètres

1. **Périmètre minimal (recommandé pour une 1ʳᵉ itération)** : chat agent + providers
   BYOK + outils Philum (MCP) + web search. Le filesystem ICM arrive dans un 2ᵉ temps.
2. **Périmètre complet** : briques 1→4 telles que décrites (le workspace ICM hébergé
   devient le dossier de travail de l'agent).
3. **Mode local plus tard** (hors périmètre 100 % cloud) : si un jour certains veulent
   leurs vrais fichiers sur disque, un harness local (type dsh) connecté à Philum en
   MCP, avec le même serveur MCP comme destination. Décision d'architecture séparée.
4. **Intégration dsh telle quelle** : écartée (stack Node, local-first, developer
   preview, ressources VM). On s'inspire, on n'embarque pas.

---

## 7. Points ouverts à trancher

**Trancés (2026-08-20)** :
- **Web search** : Firecrawl écarté (test exploratoire seulement, aucun avantage en
  exactitude). Source = API dédiée type Tavily/Exa/Brave/Serper (URLs brutes
  vérifiables) **ou** grounding natif du provider quand il existe ; les oracles
  structurés (Crossref/OpenAlex/NCBI) restent la source de vérité pour les questions
  bibliographiques.
- **Vision** : le provider est le cerveau, Philum est « les mains et la preuve » —
  le web search natif du provider est un bonus, pas une dépendance.

**Restent à trancher** :

1. **Le BYOK doit-il passer par un endpoint OpenAI-compatible unique** (une surface,
   4 providers via base_url/model différents) ou par des SDK natifs par provider ?
   Recommandation : surface OpenAI-compatible (c'est ce que fait dsh, et Gemini/DeepSeek
   l'exposent nativement) — mais valider la pertinence de cette abstraction.
2. **Streaming vs job asyncio** pour le chat : le principe Philum « jamais d'appel LLM
   synchrone dans une route HTTP » s'applique-t-il au chat temps réel, ou le streaming
   SSE borné est-il acceptable ?
3. **Approbation des écritures** : faut-il une politique d'approbation explicite (toute
   écriture Philum validée dans l'UI avant exécution) ou un mode « l'agent agit, tout est
   journalisé, l'utilisateur peut annuler » ?
4. **Stockage des clés** : côté serveur chiffré (dépend de `master_encryption_key`, un
   vol de la VM expose les clés) vs côté navigateur jamais au repos chez Philum.
5. **Web search** : quelle API dédiée exactement (Tavily / Exa / Brave / Serper) et qui
   paie le quota de l'outil de recherche de l'agent (Philum ? l'utilisateur ?) ?
6. **Filesystem ICM** : simple stockage en Postgres (table `workspace_files`) ou objet
   type git/agrégat versionné ? Volume attendu petit (quelques Mo par créateur).
7. **Compatibilité** avec le principe « le LLM propose, la crypto dispose » : toute sortie
   d'un agent qui doit entrer dans une fiche passe-t-elle par les mêmes invariants que
   les suggestions actuelles (`suggested_by_ai`/`annotated_by_ai`, validation avant
   attestation) ?
8. **Quota et coût** : le backend ne paie rien (BYOK) mais doit gérer les erreurs
   provider de l'utilisateur (clé invalide, quota épuisé) avec des messages actionnables.

---

## 8. Risques et limites assumés

- **Sécurité des clés utilisateur** : c'est le point le plus sensible. La philosophie
  dsh (clés locales, write-only) ne se transpose pas tel quel en cloud multi-tenant ;
  le stockage côté serveur doit être justifié et auditable.
- **Surface d'attaque des outils** : interdire tout outil « exécuter du code / bash ».
  Filesystem borné au workspace du créateur. Écritures Philum scopées par créateur
  (déjà en place).
- **Developer preview** : aucune dépendance à dsh en dur ; on reprend les concepts.
- **Ressources VM** : moteur d'agent in-process asyncio, partagé, borné (tours/temps/
  tokens) ; pas de process par utilisateur.
- **Défaut connu non corrigé à l'horizon** : la date du contenu sur les fiches dépend
  d'un correctif serveur (champ date de contenu distinct de `published_at`) — documenté
  `shared/pieges-vecus.md` §10. Sans lien direct avec le harness mais à connaître.

---

## 9. Ordre de construction proposé

1. **Brique 1 — Providers BYOK** : table + service + endpoint + UI réglages (testable
   seule ; rien d'autre n'en dépend).
2. **Brique 2 — Workspace ICM hébergé** : table `workspace_files` + outils
   read/write/list + seed du template.
3. **Brique 3 — Moteur d'agent** : boucle + registre d'outils (Philum MCP + web +
   filesystem) + streaming.
4. **Brique 4 — Sessions + UI chat**.

---

*Sources vérifiées dans le repo : STATE.md, .docs/17-llm-strategy.md, apps/backend/app/services/llm.py,
apps/backend/app/mcp_server/server.py, infra/litellm/config.yaml, workspaces/createur-de-fiches/*.
Harness : deepseek-ai/deepseek-harness (README, docs/architecture.md, docs/user/guide/index.md,
docs/user/guide/providers.md, docs/development.md, packages/bundle/web-app/README.md,
docs/cookbook/adding-a-tool.md).*