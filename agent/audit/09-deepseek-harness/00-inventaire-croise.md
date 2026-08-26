# Phase 1 — Inventaire croisé : dsh × Philum

> Matrice complète des capacités de deepseek-harness comparées à l'existant Philum. Pour chaque capacité : ce que dsh a, ce que Philum a, le gap, et la pertinence pour l'intégration.

---

## 1. Agent Loop

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **State machine** | `ReactLoopAgent` : idle → running → aborted → idle. 3 phases, AbortController par phase | `boucle()` : while True avec try/except. Pas de state machine | Philum n'a pas d'états formels — le statut est dérivé de `enCours` (bool) | Haute |
| **Step boundaries** | Steps distincts avec `step/start` → `step/end`. Nouvel input intercalé entre steps | Tours uniquement — pas de step sub-tour | Un tour = une requête LLM + tools. Pas de step boundary | Haute |
| **Abort coopératif** | `signal.throwIfAborted()` à chaque point de synchronisation. AbortController par phase | `asyncio.CancelledError` non géré dans `boucle()` — le broad `except Exception` l'attrape | Pas de cancellation cooperative — le task cancellation est brutal | Haute |
| **Max parallel tool calls** | `maxParallelToolCalls` avec pool borné + modèle de réordonnancement | Exécution séquentielle des tool calls | Pas de parallélisme des tools | Moyenne |
| **Waterfall extension** | 3 waterfalls : `agent/pre-step`, `agent/turn-stopping`, `agent/request` | Pas de mécanisme d'extension — le code est monolithique | Pas de hook pour plugins/middleware | Moyenne |
| **Maintenance mode** | Phase exclusive pour travail non-LLM (persistence, setup) | Pas de concept de maintenance — tout est dans le même thread | Le workspace seed et la persistence bloquent le tour | Basse |
| **Inbox-driven wake** | `send()` → inbox → `wakeDriver()`. Messages Filed via targets | `asyncio.Queue` dans le SSE endpoint | Pattern similaire mais moins structuré | Basse |

---

## 2. Tool Registry

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Pipeline 5 étages** | pre → guards → execute → post → result. Chaque stage est un waterfall | `executer_outil()` : try/except simple, pas de pipeline | Pas de pre-validation, pas de post-processing, pas de guards | **Haute** |
| **Scoped tool layers** | `ScopedLayers<ToolLayer>` avec shadowing. Chaque agent a ses outils | Registre MCP global — tous les outils pour tous les agents | Pas d'isolation d'outils par session | Moyenne |
| **Tool timeout configurable** | `timeoutMs` par tool, AbortSignal fused | Timeout HTTP fixe 60s. Pas de timeout tool | Les tools lents peuvent bloquer le tour | **Haute** |
| **Pre-execute approval** | `tools/pre-execute` waterfall → ask/deny/allow | `est_sensible()` dans agent.py — vérification manuelle | L'approval est dans le code agent, pas dans le tool pipeline | Haute |
| **Post-execute validation** | `tools/post-execute` peut remplacer/bloquer le résultat | Pas de post-validation | Un tool peut retourner n'importe quoi | Haute |
| **Lossless JSON** | `snapshotJsonValue` à chaque frontière | `json.dumps/loads` — pas de garantie d'immutabilité | Les objets peuvent être mutés après retour | Basse |
| **Code Mode** | `run_code` SDK wrapper — le modèle écrit un script | Pas de code mode | L'agent doit faire des appels tools individuels | Basse |

---

## 3. System Prompt

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Sections ordonnées** | Registry de sections avec `order` number. Chaque plugin contribue | `_SYSTEME` = string hardcoded dans agent.py | Pas de modularité — tout est dans un fichier | **Haute** |
| **Waterfall assembly** | `system-prompt/assemble` waterfall — les plugins peuvent transformer | Pas de waterfall — le prompt est construit en amont | Pas d'extensibilité | Haute |
| **Variable interpolation** | `{{variable}}` strict avec validation | F-strings Python | Pas de validation des variables | Basse |
| **Tool ordering** | `toolOrder` config avec `<unlisted-tools>` rest | Ordre d'enregistrement FastMCP | Pas de contrôle de l'ordre model-facing | Basse |
| **Runtime context injection** | Timestamp, file refs, agent instructions injectés dynamiquement | `timestamp` dans `_PRIMING` + workspace context | Injection partielle, pas dynamique | Moyenne |
| **Complete section override** | `complete: true` remplace toutes les sections | Pas de mécanisme | — | Basse |

---

## 4. LLM Runtime

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Multi-adapter registry** | Registry nommé avec remplacement atomique | `agent_providers.py` + `agent_gratuit.py` — 2 chemins séparés | Pas de registry unifié | **Haute** |
| **Waterfall streaming** | `llm/stream` waterfall — retry, replay, routing | `_appel_provider()` — appel direct, pas de middleware | Pas d'extensibilité du streaming | Haute |
| **Retry provider-routed** | `llm-retry` : exponential backoff, jitter, Retry-After | `_BACKOFF_5XX = (2.0, 5.0)` fixe + 1 retry | Retry basique, pas provider-spécifique | **Haute** |
| **Token meter** | `TokenMeter` : counting anchor-based, replay-aware | `len(json) // 4 + 8` — estimation très grossière | Les décisions de compaction sont basées sur une estimation fausse | **Haute** |
| **Block assembler** | `BlockAssembler` : delta assembly, straggler tolerance, max-token truncation | Pas de blocs — concaténation de `message_delta` | Pas de structure de contenu | Moyenne |
| **Image projection** | `projectImagesForTextModel()` strip images for text-only models | Pas de support images | — | Basse |

---

## 5. Session Management

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Event sourcing append-only** | `Session` : log append-only avec deep-freeze, surface ops | `AgentMessage` : table DB avec role/content. Pas d'event sourcing | Messages stockés mais pas les tool calls, pas les erreurs, pas les retries | **Haute** |
| **Lossless JSON boundary** | `snapshotJsonValue` à chaque append | `json.dumps/loads` | Pas d'immutabilité garantie | Moyenne |
| **Surface operations** | `surfaceOp` markers : append, replace (compaction) | `supprimer_messages_derniers()` — delete rows | Compaction = destruction, pas de remplacement par résumé | Haute |
| **Session fork** | Création d'enfant depuis un préfixe | Pas de fork | — | Basse |
| **Projection** | Projections dérivées du log (goal, plan, tokens) | Pas de projections | — | Basse |
| **Persistence** | JSONL + zstd compression | PostgreSQL via SQLAlchemy | Persistance OK mais pas event-sourced | Basse |

---

## 6. Compaction

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Auto compaction** | `compaction-basic` : threshold ratio → LLM summarization → replace | `_est_contexte_sature()` : détection marker texte → `_compacter()` : troncation | Compaction = troncation, pas de résumé | **Haute** |
| **Two-phase** | Tool-result pruning + LLM summarization | Pas de pruning — tout est envoyé | Les tool results volumineux gaspillent du contexte | Haute |
| **Retry with remeasure** | Après résumé, remesure. Si encore au-dessus, résume encore | Pas de remesure — une seule passe | La compaction peut être insuffisante | Moyenne |
| **Overflow recovery** | `CONTEXT_WINDOW_EXCEEDED` → force compaction → retry | `_est_contexte_sature()` détecte l'erreur → compaction → retry | Pattern similaire mais moins robuste | Moyenne |
| **Per-model policies** | `modelPolicies` : thresholds par provider/model | Fixe : `BUDGET_HISTORIQUE = 96_000` | Pas d'adaptation par modèle | Moyenne |
| **Manual compaction** | `compactNow()` via maintenance | `_compacter()` appelé dans la boucle | Pas de compaction manuelle | Basse |

---

## 7. Subagent System

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Multi-provider registry** | 6 providers : spawn, fork, ACP, Claude Code, Codex, DSH SDK | Pas de subagent system | L'agent ne peut pas déléguer | **Moyenne** |
| **Continuable children** | `startContinuable()` : enfants durables avec inbox | — | — | Basse |
| **Depth guard** | `assertSubagentMaxDepth()` empêche la récursion infinie | — | — | Basse |
| **Control tools** | `send_message`, `interrupt_agent`, `list_agents` | — | — | Basse |

---

## 8. Workflow Engine

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Worker-thread scripts** | Scripts JS en VM isolée avec `agent()`, `parallel()`, `pipeline()` | ICM 7 étapes en dur dans `agent_fiche.py` | Workflow = code hardcoded, pas de scripts modèles | **Moyenne** |
| **Event emission** | `workflow/start`, `workflow/end`, `workflow/phase` | Pas d'events de workflow | Pas de visibilité sur l'avancement | Moyenne |
| **Concurrency config** | `maxConcurrentAgents`, `maxTotalAgents`, `syncTimeoutMs` | Pas de config | — | Basse |

---

## 9. Goal System

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Same-session goals** | Event-sourced, CAS mutations, phase state machine (active/paused/complete/blocked) | Pas de goal system | L'agent n'a pas d'objectifs trackés | **Haute** |
| **Authority enforcement** | Direct human pour create/edit, completion authority pour complete | — | — | Moyenne |
| **Blocked threshold** | Model ne peut pas self-report blocked avant N rounds consécutifs | — | — | Basse |

---

## 10. Plan Mode

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Plan as logged state** | `exit_plan_mode` tool, plan presented for approval | `MODE_PLAN` dans agent.py : le LLM est guidé pour réfléchir avant d'agir | Plan = instruction system prompt, pas d'état persistant | **Moyenne** |
| **Interactive approval** | Plan presented over user-questions for approval/feedback | Pas d'approval du plan — le modèle décide | Pas de validation humaine du plan | Moyenne |

---

## 11. Skills

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Filesystem discovery** | Multi-root scanning, YAML frontmatter, file watching, hot-reload | Pas de système de skills | Pas de workflows réutilisables | **Haute** |
| **Ranked candidates** | project-dsh(100) < project-agents(200) < custom(300) < user(400) < bundled(500) | — | — | Moyenne |
| **Skill tool** | `skill` tool pour charger/activer | — | — | Basse |

---

## 12. Terminal PTY

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Persistent sessions** | 6 tools : open, send, read, signal, close, list. Sessions PTY persistantes | Bash one-shot via `executer_bash()` | Pas de session persistante — chaque appel fork un nouveau process | **Moyenne** |
| **Background mode** | `terminal_send` avec `run_in_background` | — | — | Basse |
| **Output truncation** | `finalizeContent` avec `maxResultBytes` | `TOOL_RESULT_MAX = 120_000` chars | Troncation présente mais en chars, pas en bytes | Basse |

---

## 13. Sandboxing

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Capability seam** | Service Definition / Provider / Consumer | Pas de sandbox | L'agent a accès complet au filesystem | **Moyenne** |
| **Platform chain** | bwrap → landlock → seatbelt → windows-acl | — | — | Basse |
| **Per-call policy** | `SandboxPolicy` : read-only, workspace-write, full-access | — | — | Basse |

---

## 14. Web Capabilities

| Capacité | dsh | Philum | Gap | Pertinence |
|---|---|---|---|---|
| **Multi-provider search** | Perplexity, Exa, DeepSeek | `web_search` : provider unique (probablement Exa ou similaire) | Pas de fallback multi-provider | **Moyenne** |
| **Content fetch** | `web_fetch` avec timeout configurable, max output | `web_fetch` dans tools.py | Présent mais moins configurable | Basse |
| **Output cap** | `fetchMaxOutputChars` (200K) | Pas de cap visible | — | Basse |

---

## 15. UI Components

| Capacité dsh | Packages dsh | Philum equivalent | Gap |
|---|---|---|---|
| Chat conversation tree | `ui-conversation` (20 fichiers) | `ChatPanel.svelte` (1 fichier, 1007 lignes) | Monolithe vs composants modulaires |
| Tool call rendering | `ui-tool` avec DisclosureRow, GenericToolCard | `ToolCard.svelte` (111 lignes) | Pas de spécialisation par tool type |
| Agent trajectory | `ui-trajectory` (13 fichiers) | Rien | **Gap majeur** |
| Plan visualization | `ui-plan` | Rien | **Gap** |
| Goal visualization | `ui-goal` (3 fichiers) | Rien | **Gap** |
| Workflow execution | `ui-workflow-run` (2 fichiers) | Rien | **Gap** |
| Settings shell | `ui-settings` + 4 sous-packages | Rien | **Gap** |
| Permission presets | `ui-permission-presets` | `ApprovalCard.svelte` | Simplicity vs richesse |
| Model selection | `ui-model-selection` + `ui-settings-models` | Selectors dans ChatPanel | Intégré vs séparé |
| Command palette | `ui-commands` | Rien | **Gap** |
| Skill browser | `ui-skill` | Rien | **Gap** |
| Subagent management | `ui-subagent` | Rien | **Gap** |
| Deliverables | `ui-deliverables` | Rien | **Gap** |
| Message feedback | `ui-message-feedback` | Rien | **Gap** |
| Sidebar navigation | `ui-sidebar` | Rien | **Gap** |
| Layout (3-col) | `ui-layout` avec drag handles | Layout simple | Gap |
| Theme system | `ui-theme` avec CSS tokens | `app.css` tokens | Similaire mais moins structuré |
| Autocomplete | `ui-input-trigger` | Rien | **Gap** |
| Focus trap / modal | `packages/interaction/` | `ConsentementGratuit.svelte` | **Bug B9** |

---

## 16. Credentials & Settings

| Capacité dsh | Philum equivalent | Gap |
|---|---|---|
| Layered credential resolution (env → store → .env) | `agent_providers.py` AES-GCM encryption | Similaire mais pas layeré |
| Namespace-scoped settings with revision tracking | Session-based settings | Pas de settings persistants |
| Conflict detection (expectedRevision) | Pas de versioning | Risque de lost-update |

---

## 17. Context Injection

| Capacité dsh | Philum equivalent | Gap |
|---|---|---|
| AGENTS.md loading with baseline identity | Workspace CONTEXT.md | Similaire mais pas de projection |
| Time context with timezone + elapsed | Timestamp dans `_PRIMING` | Présent mais pas dynamique |
| File reference (@prefix) | Rien | **Gap** |
| Session reference (cross-session) | Rien | **Gap** |

---

## 18. Jobs & Schedule

| Capacité dsh | Philum equivalent | Gap |
|---|---|---|
| Background job management (start, list, read, kill) | Rien | **Gap** |
| Scheduled tasks (one-shot, fixed-rate) | Rien | **Gap** |
| Message feedback (CRUD with versioning) | Rien | **Gap** |

---

## 19. Defensive Patterns

| Pattern dsh | Philum equivalent | Recommandation |
|---|---|---|
| Registrations are effects (disposer) | Pas de cleanup auto | Documenter |
| Model-visible equals logged | `agent_sessions` partiel | Renforcer |
| Every package owns invariant.ts | `_invariants.txt` statique | **Porter** |
| 100% per-file coverage gate | Pas de gate | **Ajouter** CI |
| Branded types | UUIDs simples | OK |
| Lossless JSON boundary | `json.dumps/loads` | OK pour Philum |
| Deep-freeze immutability | Pas d'immutabilité | Acceptable |
| Exhaustive switch (assertNever) | Pas de switch exhaustif | À adopter |
| Tests describe behavior | Tests existent | Pattern à adopter |

---

_Matrice complète — 19 domaines, 100+ capacités comparées._
