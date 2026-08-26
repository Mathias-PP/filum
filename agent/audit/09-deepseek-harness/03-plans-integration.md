# Phase 4 — Plans d'intégration détaillés

> Pour chaque feature prioritaire, le plan d'intégration avec fichiers, patterns, et dépendances.

---

## Sprint 1 — Quick Wins (F1→F18)

Voir `02-faisabilite.md` section F. Tous les quick wins sont des edits simples de 2-30 minutes chacun. Pas de plan détaillé nécessaire — ce sont des changements atomiques.

---

## Sprint 2 — Fixes critiques

### A16 — Block Assembler (streaming structuré)

**Objectif** : Structurer le flux SSE en blocs typés (text-delta, tool-call, tool-result) au lieu de concaténer `message_delta` en brut.

**dsh source** : `packages/llm/llm/src/assembler.ts` (207 lignes)

**Pattern** :
```
StreamChunk → BlockAssembler.push(chunk) → ContentBlock[] → Message
```

**Philum implémentation** :
1. Créer `agent/block_assembler.py` avec une classe `BlockAssembler` :
   - `push(chunk: dict)` — acumule les deltas
   - `blocks()` → `list[ContentBlock]` — retourne les blocs assemblés
   - `message()` → `Message` — retourne le message final
   - `interrupted_blocks()` — retourne les blocs non terminés

2. Modifier `agent.py` pour utiliser le block assembler au lieu de la concaténation directe

3. Modifier `conversation.ts` pour typer les events (assistant/text, assistant/tool-call, assistant/tool-result)

**Fichiers** :
- Nouveau : `apps/backend/app/services/block_assembler.py`
- Modifier : `apps/backend/app/services/agent.py` (utiliser le assembler)
- Modifier : `apps/frontend/src/lib/agent/conversation.ts` (events typés)

**Effort** : 1 jour

---

### A6 — Token Meter (context tracking)

**Objectif** : Remplacer `len(json)//4+8` par un comptage tokens précis avec anchor-based diffing.

**dsh source** : `packages/llm/token-meter/src/index.ts` (313 lignes)

**Pattern** :
```
Session events → incremental fold → surfaceTokens (cumulative)
Anchor (dernier provider usage) → delta tokens depuis l'anchor
```

**Philum implémentation** :
1. Créer `agent/token_meter.py` :
   - `class TokenMeter` avec `measure(messages) -> TokenEstimate`
   - Utiliser `tiktoken` ou estimation par caractère (ratio 3.5 pour EN, 1.5 pour FR/CN)
   - Anchor-based : après chaque réponse LLM avec `usage`, enregistrer l'anchor
   - Delta depuis l'anchor au lieu de tout ré-estimer

2. Modifier `agent.py` pour utiliser le meter avant chaque appel LLM
3. Modifier `agent_sessions.py` pour stocker les `usage` tokens

**Fichiers** :
- Nouveau : `apps/backend/app/services/token_meter.py`
- Modifier : `apps/backend/app/services/agent.py` (utiliser le meter)
- Modifier : `apps/backend/app/services/agent_sessions.py` (stocker usage)
- Modifier : `requirements.txt` (ajouter `tiktoken`)

**Effort** : 1 jour

---

### A15 — Context Compaction améliorée

**Objectif** : Remplacer la troncation par un résumé LLM + tool-result pruning.

**dsh source** : `packages/compaction/compaction-basic/src/index.ts` (431 lignes)

**Pattern** :
```
Token pressure > threshold → toolResultPruner (réduit les résultats tools) → LLM summarization → replace shadowed events
```

**Philum implémentation** :
1. Modifier `_compacter()` dans `agent.py` :
   - Phase 1 : Pruning des tool results les plus anciens/tronquer les plus gros
   - Phase 2 : Demander au LLM de résumer les messages à compacter
   - Phase 3 : Remplacer les messages originaux par le résumé

2. Utiliser le token meter (A6) pour déclencher la compaction

3. Ajouter `compaction_threshold` et `compaction_retain` comme config

**Fichiers** :
- Modifier : `apps/backend/app/services/agent.py` (refactor `_compacter`)
- Modifier : `apps/backend/app/services/agent_sessions.py` (support résumé)

**Effort** : 1.5 jours

---

### A2 — System Prompt waterfall

**Objectif** : Modulariser le prompt en sections ordonnées contribuées par différents modules.

**dsh source** : `packages/core/system-prompt/src/index.ts` (545 lignes)

**Pattern** :
```
SectionRegistry → sections avec order number → tri par order → assemblage
```

**Philum implémentation** :
1. Créer `agent/prompt_sections.py` :
   - `class PromptSectionRegistry`
   - `register(name, order, text_fn)` — enregistre une section
   - `assemble() -> str` — trie et assemble

2. Chaque module enregistre ses sections :
   - `agent.py` : persona (order 0)
   - `tools.py` : tool descriptions (order 100)
   - `agent_workspace.py` : workspace context (order 200)
   - `agent_fiche.py` : fiche workflow (order 300)
   - Futur : skills, plan, goal

3. Remplacer `_SYSTEME` hardcoded par `registry.assemble()`

**Fichiers** :
- Nouveau : `apps/backend/app/services/prompt_sections.py`
- Modifier : `apps/backend/app/services/agent.py` (utiliser registry)
- Modifier : chaque module qui contribue au prompt

**Effort** : 1 jour

---

### A23 — Retry provider-routed

**Objectif** : Retry avec exponential backoff, jitter, et Retry-After provider-spécifique.

**dsh source** : `packages/llm/llm-retry/src/index.ts` (226 lignes)

**Pattern** :
```
agent/request-error → retry policy → cancellable delay → retry ou abort
```

**Philum implémentation** :
1. Créer `agent/retry_policy.py` :
   - `class RetryPolicy` avec `max_retries`, `initial_delay`, `max_delay`, `jitter_ratio`
   - `retryable_codes: list[str]` — codes retryables par provider
   - `delay(retry_count) -> float` — exponential backoff avec jitter

2. Modifier `_appel_provider()` pour utiliser le retry policy
3. Ajouter support `Retry-After` header

**Fichiers** :
- Nouveau : `apps/backend/app/services/retry_policy.py`
- Modifier : `apps/backend/app/services/agent.py`

**Effort** : 0.5 jour

---

## Sprint 3 — Nouvelles capacités

### A3 — Goal system

**dsh source** : `packages/goal/goal/src/index.ts` (592 lignes) + `tool-goal/src/index.ts` (338 lignes)

**Philum implémentation** :
1. Nouveau model DB `AgentGoal` :
   - `id`, `session_id`, `objective`, `phase` (active/paused/complete/blocked), `revision`, `created_at`, `updated_at`
2. Tools MCP : `create_goal`, `get_goal`, `update_goal`
3. Injection dans le system prompt
4. UI : `GoalBar.svelte` inspiré de dsh

**Effort** : 3 jours

---

### A4 — Skills filesystem

**dsh source** : `packages/skill/skill-filesystem/src/index.ts` (1041 lignes)

**Philum implémentation** :
1. Répertoire `skills/` à la racine du repo avec fichiers `.md`
2. YAML frontmatter : `name`, `description`, `triggers`
3. Discovery au boot + file watching (via `watchdog`)
4. Tool MCP : `list_skills`, `load_skill`
5. Injection dans le system prompt

**Effort** : 2 jours

---

### A14 — Session event sourcing

**dsh source** : `packages/core/session/src/index.ts` (1157 lignes)

**Philum implémentation** :
1. Nouveau model `AgentEvent` :
   - `session_id`, `seq`, `type` (turn/start, step/start, user/message, assistant/message, tool/call, tool/result, etc.), `data` (JSON), `created_at`
2. Chaque action dans l'agent loop append un event
3. Reconstruction de l'historique depuis les events
4. Compaction = replace events (pas de delete)

**Effort** : 5 jours (migration DB + refactor agent.py)

---

### A9 — Background jobs

**dsh source** : `packages/jobs/src/index.ts` (179 lignes)

**Philum implémentation** :
1. Nouveau model `AgentJob` :
   - `id`, `session_id`, `status` (pending/running/completed/failed), `result` (JSON), `created_at`
2. Tools MCP : `job_list`, `job_output`, `job_kill`
3. Utilisé pour les long-running tasks (rebuild_graph, archive_sources, etc.)

**Effort** : 2 jours

---

## Sprint 4 — UI/UX

### A24 — SSE reconnection

**Philum implémentation** :
1. `agent.ts` : ajouter `Last-Event-ID` header
2. `agent_chat.py` : support `Last-Event-ID` pour reprise
3. `ChatPanel.svelte` : auto-retry sur déconnection avec backoff
4. UI : indicateur "Reconnexion..." pendant le retry

**Effort** : 1 jour

---

### A21 — File reference (@prefix)

**Philum implémentation** :
1. Frontend : détecter `@` dans l'input → autocomplete avec fichiers workspace
2. Backend : tool `list_workspace_files` pour recherche
3. Injection dans le system prompt

**Effort** : 1 jour

---

## Sprint 5 — Avancé

### B3 — Subagent providers multiples

**Philum implémentation** :
1. ABC `SubagentProvider` avec `execute(request) -> Result`
2. Providers : `LocalProvider` (actuel), `DshProvider` (via JSON-RPC), `ExternalProvider` (via HTTP)
3. Tool MCP : `delegate_to_agent(provider, request)`
4. UI : `SubagentHeader.svelte` inspiré de dsh

**Effort** : 5 jours

---

### B4 — Terminal PTY persistant

**Philum implémentation** :
1. `asyncio.create_subprocess_exec` avec PTY via `pty` module
2. Sessions persistantes avec output buffer
3. Tools MCP : `terminal_open`, `terminal_send`, `terminal_read`, `terminal_close`
4. Output truncation configurable

**Effort** : 3 jours

---

## Estimation totale

| Sprint | Effort | Priorité |
|---|---|---|
| Sprint 1 — Quick wins | 3.5 heures | Immédiate |
| Sprint 2 — Fixes critiques | 5 jours | Haute |
| Sprint 3 — Nouvelles capacités | 12 jours | Haute |
| Sprint 4 — UI/UX | 2 jours | Moyenne |
| Sprint 5 — Avancé | 8 jours | Basse |
| **Total** | **~27 jours** | |

---

_Plans détaillés pour chaque sprint — fichiers, patterns, dépendances._
