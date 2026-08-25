# 2026-08-20 — Comparatif six repos : ce qu'on copie / adapte pour le harness BYOK Philum

> **Objet** : six repos explorés en profondeur (code vérifié au 2026-08-20) pour extraire ce
> qui est **copiable tel quel**, ce qui est **adaptable**, et ce qu'on **ignore**, pour la
> fonctionnalité harness d'agent BYOK de Philum (chat LLM + workspace ICM hébergé + fiches
> automatisées). Repos : `digipair`, `deepseek-harness`, `rakazo`,
> `Interpretable-Context-Methodology`, `icm-architect`, `ecc`.
>
> **Contexte** : les décisions produit/architecture actées le 2026-08-20 (rapport
> `2026-08-20-harness-agent-philum.md`) restent inchangées. Ce rapport les complète avec le
> détail de **comment** implémenter, en s'appuyant sur des patterns prouvés.
>
> Clones locaux : `%TEMP%\opencode\repos\{digipair, deepseek-harness, rakazo, icm,
icm-architect, ecc}`.

---

## 1. Tableau de synthèse

| Repo                 | Nature                                                      | Licence                 | Pertinence Philum    | Verdict                                                                                                                    |
| -------------------- | ----------------------------------------------------------- | ----------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **rakazo**           | Bots persistants BYOK + Pi, Electron/Expo/web, Postgres     | Apache-2.0              | **Très haute**       | **Source n°1 de patterns** : run state machine, secrets AES-256-GCM, approbation hybride, idempotence d'outils, compaction |
| **deepseek-harness** | Harness d'agent local-first (Node)                          | MIT                     | Haute (concepts)     | Couche BYOK multi-provider (pi-ai), seam de credentials, approval fail-closed. **Non embarqué** (déjà décidé)              |
| **digipair**         | Framework de raisonnement basé sur des fichiers JSON (PINS) | (propriétaire de conso) | Moyenne              | Language JSON typé + merge hiérarchique de configs + schéma→outils MCP                                                     |
| **ICM**              | Méthodologie « la structure de dossiers orchestre l'agent » | MIT                     | Haute (déjà adoptée) | Conventions 15 patterns ; le workspace `createur-de-fiches` est déjà un ICM                                                |
| **icm-architect**    | Skill de construction/restructuration d'espaces ICM         | MIT                     | Moyenne              | 10 invariants + walk test + 6 formes — utile pour **valider** les workspaces hébergés                                      |
| **ecc**              | Pack d'agents/skills/hooks pour harness de codage           | MIT                     | Moyenne              | GateGuard, regex-vs-LLM, memory vault, AgentShield — patterns à transférer, pas le code                                    |

---

## 2. rakazo — la source n°1 des patterns à copier

Repo le plus proche de la cible Philum : bots persistants, BYOK, mémoire, routines, sandbox.
Tout est vérifié dans le code.

### 2.1 Secrets : AES-256-GCM — déjà identique à KeyManager

`packages/adapters/src/secrets.ts` (`EncryptedSecretStore`) :

- Clé = `sha256(encryptionKey)` (32 octets).
- `put()` : `iv(12B) + authTag(16B) + ciphertext`, le tout base64. `load(ciphertext)` explicite ;
  `get()` **jette** (pas de lookup par id) — on force l'appelant à posséder le ciphertext.
- `redact(value)` : regex sur `sk-*` et JWT `eyJ...` → `[redacted]`.

C'est exactement le schéma `app/crypto/keygen.py` de Philum. À copier tel quel (en Python) :
**on ne stocke jamais de clé en clair ; la clé déchiffre en mémoire le temps d'une opération.**

### 2.2 Credentials BYOK en base

`packages/db/src/model-credentials.ts` + `executor.ts` (`resolveModelKey`) :

- Table `userModelCredential` : `(userId, workspaceId, provider, defaultModel, isDefault, secretId)` —
  la **référence** vit en clair, la **valeur** est dans une table `secret` chiffrée.
- `resolveModelKey` : charge le ciphertext, `secretStore.load()`, résout (refresh OAuth si < 5 min de
  validité), et **réécrit** le token rafraîchi chiffré. Verrou par `secretId` (mutex mémoire) pour
  éviter les écritures concurrentes.
- **Fallback** : `deploymentModelKey` (clé Philum, ex. OpenRouter) quand l'utilisateur n'a pas de
  credential — copie la décision Philum « le provider par défaut utilise la clé plateforme ».
- Enregistre les valeurs résolues dans une liste `runSecrets` qui sert à la **redaction en flux**.

### 2.3 Machine à états de run — approbation hybride

`packages/adapters/src/executor.ts` (`continueRun`) :

- Statuts : `queued → leased → running → waiting_input / waiting_takeover → completed|failed`,
  plus `leased`/`running` relouables si `leaseExpiresAt ≤ now`.
- **Lease** : `leaseOwner` (workerId), `leaseFence` (incrément), `leaseExpiresAt` (5 min), heartbeat de
  renouvellement toutes les 60 s. Chaque reprise crée un `attempt`. Retry de computer occupé avec
  backoff `250 × 2^fence` (cap 10 s).
- **`ask` event → `pauseRunForInput`** : le run passe `waiting_input`, message notifié à l'utilisateur,
  l'UI répond, `continueRun` relance. C'est **exactement** l'approbation hybride Philum : les écritures
  réversibles se font en auto, les actions sensibles déclenchent un `ask` et suspendent le run.
- `waiting_takeover` : variante où le bot rend l'écran à l'humain (hors périmètre Philum MVP).

### 2.4 Ne jamais persister un secret dans la conversation

`executor.ts` :

- `createStreamingRedactor(runSecrets)` — redige le texte **pendant le streaming** vers l'UI.
- Avant d'écrire le message final : `containsSecret(text, runSecrets)` → si vrai, **throw** :
  « refusing to persist a secret in the thread ». La conversation ne peut pas contenir un secret, même
  si le LLM le « leak ». C'est le garde-fou non négociable à copier.

### 2.5 Idempotence d'effets d'outils

`executor.ts` (`recordEffect`/`completeEffect`) :

- Table `externalEffect` : `(runId, kind, idempotencyKey = executionId, status intended→completed, request, result)`.
- À la reprise d'un run, un outil déjà exécuté (même `executionId`) renvoie le résultat stocké au lieu
  de ré-exécuter ; si le statut n'est pas `completed`, il **jette** (« uncertain outcome ») pour les outils
  non idempotents. Outils read-only (`computer_observe`, `list_files`, `read_file`, `request_takeover`,
  `run_subagent`) exemptés.

→ Pour Philum : les outils du serveur MCP doivent être classés read-only / idempotent / non-idempotent,
et l'effet tracé avant exécution. C'est ce qui rend les retries sûrs.

### 2.6 Boucle d'agent (runtime Pi)

`packages/adapters/src/pi-runtime.ts` :

- Streaming via **file d'événements** (`text`, `tool`, `subagent`, `usage`, `done`) consommée par
  l'exécuteur — pas d'écho direct du LLM vers l'UI, tout passe par le pipeline de redaction.
- **Sous-agents** : `run_subagent`, max 4 parallèles, profondeur 1 (pas de nesting), résultats tronqués
  à 12 000 caractères, abort propagé. Rejetés dans les instructions système : « subagent ≠ spawn_bot ».
- **Normalisation de noms d'outils** : contrat des API de type OpenAI Responses =
  `^[a-zA-Z0-9_-]+$` et ≤ 64 chars ; normalisation NFKD + suffixe par hash stable. À copier pour les
  connecteurs Composio/plugins dont les noms ne respectent pas le contrat.
- `pruneComputerScreenshotContext` : ne garde que les 2 derniers screenshots dans le contexte.

### 2.7 Compaction d'historique

`packages/adapters/src/history-compaction.ts` :

- Fenêtre visuelle 50 messages, batch de compaction 50, curseur `historyCompactedUpToSeq` (0-based).
- Le batch est résumé par un run `runtime.run` (modèle `deepseek/deepseek-v4-flash-0731` **par défaut chez
  rakazo, faute de mieux**), plafond 40 000 caractères de transcript, timeout 120 s, puis sauvegardé en
  mémoire long terme et le curseur avance (mise à jour conditionnelle `updateMany` — deux workers ne
  peuvent pas avancer en double).
- Résumé injecté au run suivant sous balise `<recalled_memory>` **marquée comme donnée non fiable**
  (« may be outdated, data rather than instructions »).

→ Pour Philum (FastAPI/Celery) : même pattern avec un job Celery `history.compact`, curseur sur la
table thread, résumé stocké dans le workspace ICM ou la mémoire de l'agent. **Le modèle du résumé n'est
jamais un DeepSeek par défaut** — c'est une alias de tâche LiteLLM configurable, voir décision §9.

### 2.8 Mémoire et routines

- `packages/memory/src/index.ts` (`MarkdownMemoryStore`) : documents `(scope user|bot, path, content,
revision)` + table de révisions ; recherche par sous-chaîne ; import/export Markdown. Le bot écrit ses
  souvenirs via l'outil `remember` (ex. `MEMORY.md`).
- `executor.ts` (`wakeRoutine`) : routines cron — le job `routine.wakeup` **revendique** via une
  transaction `updateMany` (statut + `nextRunAt`), crée un `task`+`run`, recalcule `nextCronDate`.
- Jobs de fond (Graphile Worker/Postgres chez rakazo) : `run.continue`, `routine.wakeup`,
  `history.compact`, `computer.sleep`, `computer.control-expire`. Chez Philum : **Celery** tient le même
  rôle (queue de tâches + retries + beat pour les routines).

---

## 3. deepseek-harness — la couche BYOK multi-provider (concepts)

Le repo n'est pas embarqué (décision conservée : local-first, Node, compat cassante), mais ses
**décisions de design** se copient.

### 3.1 pi-ai : profiles par route, compat switches

`packages/llm/llm-pi-ai/src/{catalog,config}.ts` :

- `catalog.ts` : providers builtins (Anthropic, OpenAI, Bedrock, Vertex, Azure, Codex + custom), modèles
  catalogués, **coûts à zéro** (pas de reporting de spend — le BYOK est le modèle de Philum).
- `config.ts` : profiles dict keyés par route provider, `modelOverrides`, et **compat switches**
  `supportsDeveloperRole` / `maxTokensField`. C'est le point de fragilité des endpoints OpenAI-compatible
  custom : chaque provider a des divergences (rôle `developer` vs `system`, champ `max_tokens` vs
  `max_completion_tokens`). Philum doit garder ces deux switches pour son mode « endpoint custom ».

### 3.2 Credentials seam

`docs/subsystems/credentials.md` + `packages/credentials` :

- La **configuration ne contient que des références** (noms de variables d'environnement), jamais les
  valeurs ; le provider détient les valeurs ; **résolution par opération** (rotation à chaud, sans
  restart) ; clés write-only (`$DSH_HOME/.credentials.yaml`) ; **valeur vide = absente partout**.

### 3.3 Approval fail-closed

`docs/subsystems/approval.md` + `packages/interaction/user-approval` :

- Outcomes fermés : `allowed-once | rejected | cancelled | unavailable` (pas de défaut ouvert).
- Événements d'audit **pairés** `approval/asked` + `approval/decided`, politique `ask`/`never` par session.
- C'est la version « dsh » de l'approbation hybride rakazo. Les deux convergent vers le même design :
  **l'outil sensible suspend le run et attend une décision explicite de l'utilisateur**.

### 3.4 À retenir en plus

- **Tool catalog généré** (`docs/tool-catalog.md`) : le registre d'outils du serveur MCP Philum
  (~30 outils) mérite le même artefact de doc auto-généré.
- **web-search-deepseek** : tool serveur natif `web_search_20250305` via API Anthropic-compatible
  (`https://api.deepseek.com/anthropic/v1`) — confirme que Philum peut brancher les web search natifs
  provider par provider via des adaptateurs.
- **Python SDK** (`deepseek-harness-sdk`) : pilote le runtime en sous-processus JSON-RPC stdio. C'est la
  preuve qu'un client Python peut piloter un agent Node — mais Philum a tranché : on garde une boucle
  d'agent **maison** en Python, pas d'embarquement.

---

## 4. digipair — le langage PINS et le merge de configs

`apps/factory` + `libs/engine` + skills.

### 4.1 PINS : un langage JSON typé de raisonnement

`libs/engine/src/lib/pins-settings.interface.ts` : `PinsSettings { library, element, properties,
conditions { if / each }, pins, events }`. Le moteur (`engine.ts`) exécute les `pins` récursivement avec
évaluation Handlebars + FEEL/CEL (`EVALUATE:`, `FEEL:`, `CEL:`, `NOEVAL:`).

→ Pour Philum : utile uniquement si on veut une **spécification déclarative** des raisonnements d'agent.
Le workspace ICM (fichiers Markdown + conventions) couvre déjà ce besoin avec plus de transparence.
**Verdict : ignorer le moteur, retenir l'idée** qu'un raisonnement peut être une donnée déclarative.

### 4.2 Merge hiérarchique des configs + BYOK via `privates`

`apps/factory/src/app/app.service.ts` : merge `default → common → role → agent` ; secrets par digipair
dans `privates` ; skill-openai lit `context.privates.OPENAI_API_KEY` + `OPENAI_SERVER` (baseURL).

→ Copier le **principe de fusion hiérarchique** pour la config des agents Philum (UI + fichiers) :
défauts plateforme → commun → agent → run. C'est le pendant « fichier » du layer 3 ICM.

### 4.3 Schéma JSON → outils MCP

`skill-llm` (`withStructuredOutput(jsonSchemaToZod(schema))`) et `skill-mcp` (`createServer` expose les
raisonnements comme outils MCP depuis schema.json). Confirme le pattern Philum : **le serveur MCP est le
registre d'outils, le JSON Schema est le contrat de chaque outil.**

---

## 5. ICM + icm-architect — la méthodologie déjà adoptée, à durcir

Le workspace Philum `workspaces/createur-de-fiches/` est déjà un ICM (7 étapes, `runs/{slug}/` par run).
Ce que les deux repos apportent en plus :

### 5.1 Les conventions (15 patterns)

`_core/CONVENTIONS.md` : contrats de stage Inputs/Process/Outputs, handoffs par `output/`, références à
sens unique, **routage sélectif de sections**, **sources canoniques** (chaque info a une seule maison),
questionnaire plat « tout d'un coup », niveau système, checkpoints (pauses humaines), audits de stage
(pass/fail non ambigu), docs sur outputs (« les outputs passés ne sont pas des templates »).

→ Déjà en grande partie dans `createur-de-fiches` (ex. `shared/principes-editoriaux.md`, garde-fous,
`_core/audit/audit_fiche.py`). **Vérifier la conformité** via le walk test (5.2) et combler les trous
(sources canoniques, routage sélectif).

### 5.2 icm-architect : invariants + walk test

`icm-architect/SKILL.md` : 10 invariants (un dossier = un job, fichier d'entrée petit et stable,
numérotation = ordre, contrat explicite par dossier, factory vs product, chaque output est une surface
d'édition, ne charger que le nécessaire, texte + frontmatter, le filesystem est la machine à états,
instancier par copie de template) et le **walk test** : un agent froid doit pouvoir, avec le fichier
d'entrée + ≤ 2 lectures, savoir où aller et quoi produire ; le statut doit être dérivable en scannant les
`output/`.

→ Pour Philum : le **walk test devient un test automatisé** du workspace hébergé (le MCP server ou un job
valide qu'un espace ICM fraîchement copié est « marchable » avant de le proposer au créateur).

### 5.3 Limitations assumées (à garder en tête)

Réal-time multi-agent, haute concurrence multi-utilisateurs, branchement automatisé en milieu de pipeline :
ICM n'est pas fait pour ça. Philum héberge des runs ICM **séquentiels et revus par l'humain** — c'est
dans le périmètre. Le « branchement » reste une décision humaine entre étapes (checkpoints).

---

## 6. ECC — des patterns à transférer, pas du code

`ecc` est un pack massif (68 agents, 286 skills, 94 commandes) pour des **harnesses CLI de codage** ; le
code n'est pas réutilisable chez Philum (serveur, pas CLI). Mais trois skills sont directement
transférables comme principes :

### 6.1 GateGuard — « enquêter avant d'écrire »

`skills/gateguard/SKILL.md` : gate en 3 temps (DENY → FORCE les faits → ALLOW). L'auto-évaluation ne
marche pas (« are you sure? » → toujours « oui ») ; l'**investigation forcée** (lister les importeurs,
citer la consigne utilisateur, montrer le schéma de données) améliore la qualité (+2.25 points A/B).

→ Pour Philum : transformer en **guard d'outil MCP** pour les écritures sensibles : avant d'écrire un
fichier de fiche, l'agent doit présenter les faits (source vérifiée, extrait verbatim, check editorial
— cf. `principes-editoriaux.md`). C'est l'approbation hybride « avant », du côté outil.

### 6.2 Regex-vs-LLM — structurer sans payer le LLM partout

`skills/regex-vs-llm-structured-text/SKILL.md` : regex gère 95-98 % des cas ; score de confiance ; LLM
(couches bon marché) seulement pour les cas < seuil. Mesures de prod : 8/410 items basse confiance, ~95 %
de coût évité.

→ C'est la validation numérique de la stratégie Philum : **oracles structurés + scraping maison d'abord,
LLM seulement pour la vérification/bas-score**. À citer tel quel dans les docs d'architecture.

### 6.3 Memory vault + AgentShield

- `skills/unified-memory/SKILL.md` : vault Markdown scopes `project/team/user`, « rappeler avant
  d'écrire », contexte rappelé = **non fiable** (jamais de règles), frontmatter de confiance. Confirme la
  conception mémoire de rakazo (2.7) et l'ICM.
- `skills/security-scan/SKILL.md` (AgentShield) : scanner la config agent (CLAUDE.md, mcp.json, hooks,
  agents) pour secrets en dur, injection de prompt, serveurs MCP risqués. → Chez Philum : à réutiliser
  comme idée pour **scanner les workspaces ICM soumis par les créateurs** (une fiche/source peut contenir
  une injection de prompt — la balise `<recalled_memory>` « data not instructions » de rakazo est la même
  défense).

---

## 7. Synthèse — copier / adapter / ignorer

### Copier tel quel (transposition Python/backend)

| Pattern                                                                                    | Source                                          | Où l'injecter                                                                      |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| AES-256-GCM `iv(12)+tag(16)+ct` base64, `load()` explicite                                 | rakazo `secrets.ts`                             | `app/crypto` (KeyManager déjà conforme)                                            |
| Redaction streaming + `containsSecret` qui refuse de persister                             | rakazo `executor.ts`                            | pipeline d'agent Philum (chat + fiche)                                             |
| Machine à états run `queued→leased→running→waiting_input`, lease+fence+heartbeat, attempts | rakazo `executor.ts`                            | service d'agent FastAPI (Celery worker)                                            |
| `ask` → suspension du run + notification → `continueRun`                                   | rakazo `executor.ts`                            | approbation hybride (MVP : actions sensibles validées)                             |
| Idempotence d'effets par `executionId`, outil read-only/idempotent/non                     | rakazo `executor.ts`                            | serveur MCP (~30 outils classés)                                                   |
| Fenêtre+compaction d'historique avec curseur, job de fond, 40k/120s                        | rakazo `history-compaction.ts`                  | job Celery + mémoire d'agent (modèle interne : jamais DeepSeek par défaut, cf. §9) |
| Credentials BYOK : ref en clair + valeur chiffrée + verrou + fallback clé plateforme       | rakazo `model-credentials.ts`/`resolveModelKey` | `app/services` (BYOK)                                                              |
| Compat switches `supportsDeveloperRole`/`maxTokensField` + profiles par route              | dsh `llm-pi-ai/config.ts`                       | `app/services/llm.py` (LiteLLM + mode custom)                                      |
| Normalisation de noms d'outils (`^[a-zA-Z0-9_-]{1,64}$`)                                   | rakazo `pi-runtime.ts`                          | connecteurs/composio du MCP                                                        |
| Walk test automatisé des workspaces ICM                                                    | icm-architect `SKILL.md`                        | job de validation des espaces hébergés                                             |
| Regex d'abord, LLM sur bas-score seulement (0.95)                                          | ecc `regex-vs-llm-structured-text`              | pipeline d'extraction/vérification (confirme oracles)                              |

### Adapter (même idée, implémentation Philum)

| Pattern                                                                | Source                        | Adaptation                                                    |
| ---------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------- |
| Sous-agents max 4, profondeur 1, troncature 12k                        | rakazo `pi-runtime.ts`        | sous-tâches de recherche/vérification par run (Celery groups) |
| Routines cron revendiquées en transaction + `nextCronDate`             | rakazo `wakeRoutine`          | Celery beat + jobs `routine.wakeup`                           |
| Merge hiérarchique de configs `default→common→role→agent`              | digipair `app.service.ts`     | config agents Philum (UI + fichiers ICM)                      |
| GateGuard « enquêter avant d'écrire »                                  | ecc `gateguard`               | guard MCP sur écritures sensibles (check editorial d'abord)   |
| Injection de contexte rappelé marquée non fiable (`<recalled_memory>`) | rakazo `formatRecalledMemory` | mémoire d'agent + source contenue dans une fiche              |
| OAuth device-code BYOK (ChatGPT Plus/Copilot/SuperGrok)                | rakazo `pi-oauth.ts`          | phase post-MVP (MVP = clés API chiffrées)                     |

### Ignorer

| Élément                                                                 | Source   | Pourquoi                                                           |
| ----------------------------------------------------------------------- | -------- | ------------------------------------------------------------------ |
| Moteur PINS (FEEL/CEL/Handlebars)                                       | digipair | l'ICM couvre le besoin avec plus de transparence                   |
| Embarquement de `deepseek-harness` (Node, Cordis, local-first)          | dsh      | décision actée le 2026-08-20 ; concepts seulement                  |
| Electron/Expo, sandbox desktop (computer_observe/act), takeover d'écran | rakazo   | hors périmètre Philum (web/cloud, pas de machines par utilisateur) |
| Pack ECC complet (hooks CLI, 68 agents, 286 skills)                     | ecc      | cible des harnesses CLI de codage, pas un backend                  |
| Supermemory externe                                                     | rakazo   | remplacé par la mémoire d'agent Philum (Postgres + workspace ICM)  |

---

## 8. Conséquences pour le plan d'implémentation

Le plan 5 phases (`2026-08-20-harness-agent-byok.md`) se précise :

1. **Phase 1 (MVP)** — clés API chiffrées : patterns 2.1, 2.2 (ref en clair + valeur chiffrée + fallback),
   3.1 (compat switches). Rien à inventer : rakazo a déjà résolu chaque cas.
2. **Phase 2 (chat BYOK)** — pipeline de run : 2.3 (machine à états), 2.4 (redaction + containsSecret),
   2.5 (idempotence), 2.7 (compaction), sous-agents adaptés.
3. **Phase 3 (agents de fiche automatisés)** — workspace ICM hébergé : walk test (5.2), GateGuard adapté
   en guard MCP (6.1), regex/oracles + LLM bas-score (6.2).
4. **Phase 4 (approbation hybride UI)** — l'event `ask`/`waiting_input` de rakazo est le squelette exact ;
   le rapporter tel quel.
5. **Phase 5 (web search au choix de l'utilisateur)** — adaptateurs par provider (3.4), le natif comme
   bonus, les oracles Philum comme vérité.

**Risques à surveiller** : la machine à états + leases est le composant le plus délicat à transposer en
FastAPI/Celery (le lease « fence » remplace l'idempotence de Celery — à tester dès la phase 2) ; les
limites ICM (pas de branchement automatique) doivent rester des contraintes produit assumées.

---

## 9. Décision : pas de DeepSeek en modèle par défaut (souveraineté)

**Décision utilisateur (2026-08-20)** : Philum est un projet souverain ; on ne transfère pas par défaut
des données vers DeepSeek (Chine) via le cloud, l'usage fait par la Chine des données étant incertain.
DeepSeek reste acceptable **en dernier recours, avec avertissement utilisateur explicite**.

Cette décision vaut pour **tous les appels LLM initiés par la plateforme** — ce qui, en BYOK, se limite
aux **tâches internes** quand le créateur n'a pas branché son propre modèle (ex. résumé de compaction,
mémoire, plus tard synthèses/chat par défaut). Les appels de l'agent BYOK, eux, utilisent toujours le
compte du créateur : aucune donnée ne passe chez un tiers choisi par Philum.

**Ordre du choix du modèle interne** (alias de tâche LiteLLM, configurable par l'admin) :

1. **Le modèle du créateur** (BYOK) — priorité absolue : la tâche interne tourne sur son compte, aucune
   donnée chez un tiers de Philum.
2. **Fallback plateforme européen** — **Mistral** en premier choix (hébergement UE, souveraineté) ; à
   défaut un modèle **américain** (Anthropic/OpenAI/Gemini, hébergement US régi par des accords
   transatlantiques de protection des données).
3. **DeepSeek en dernier recours** — uniquement si l'utilisateur le demande explicitement pour cette
   tâche, avec un **avertissement** affiché sur la souveraineté/transfert des données.

**Conséquences dans ce rapport** :

- §2.7 : le « deepseek par défaut » de rakazo est un **anti-modèle** pour Philum — ne pas le copier,
  le remplacer par l'ordre ci-dessus (alias LiteLLM).
- §2.2 : le fallback `deploymentModelKey` chez Philum pointe donc vers l'alias de tâche interne (§9),
  jamais directement vers un provider DeepSeek.
- §3.4 : le `web-search-deepseek` natif ne se branche que si **l'utilisateur a connecté DeepSeek en
  BYOK** (même logique d'avertissement à l'ajout du provider).
- Le fournisseur DeepSeek reste présent dans la liste BYOK des 4 providers (décision produit inchangée) ;
  la souveraineté pèse sur les **défauts plateforme**, pas sur le choix du créateur.
