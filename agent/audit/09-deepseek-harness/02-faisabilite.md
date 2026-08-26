# Phase 3 — Faisabilité et priorisation

> Chaque item (bug fix + feature) catégorisé : F (quick win), A (port direct), B (adaptation), C (inspiration), D (hors périmètre).

---

## F — Quick wins (fix faciles, valeur immédiate)

| # | Item | Effort | Fichiers | Bug corrigé |
|---|---|---|---|---|
| F1 | `break-words` sur user messages | 5 min | `ChatPanel.svelte:816` | B10 |
| F2 | `max-h-[60vh] overflow-y-auto` sur code blocks | 10 min | `AgentMarkdown.svelte:56` | B11 |
| F3 | `max-h` sur ToolCard expanded | 10 min | `ToolCard.svelte:96` | B12 |
| F4 | `role="alert"` sur erreurs + retry button | 15 min | `ChatPanel.svelte:876` | — |
| F5 | `aria-busy` sur container streaming | 5 min | `ChatPanel.svelte:780` | B16 |
| F6 | `aria-expanded` sur ToolCard toggle | 5 min | `ToolCard.svelte:56` | B17 |
| F7 | `text-info` au lieu de `text-blue-600` | 2 min | `+error.svelte:19` | B20 |
| F8 | Focus trap + Escape + backdrop click | 30 min | `ConsentementGratuit.svelte` | B9 |
| F9 | `touch-action: manipulation` sur textarea | 5 min | `ChatPanel.svelte` | — |
| F10 | UTC utility `utcnow_naive()` | 10 min | Nouveau utilitaire | B6 |
| F11 | LIKE injection échappement | 15 min | `tools_write.py:1274` | B5 |
| F12 | `rebuild_graph` auth requirement | 5 min | `server.py:753` | B7 |
| F13 | `setTimeout` → request lifecycle | 30 min | `ChatPanel.svelte:870` | B4 |
| F14 | Request timeout global sur boucle() | 20 min | `agent.py:911` | B8 |
| F15 | `asyncio.CancelledError` handling | 15 min | `agent.py:1072` | — |
| F16 | Atomic quota consumption | 15 min | `agent_gratuit.py:340` | B1 |
| F17 | Transient provider guard | 10 min | `agent_gratuit.py:107` | B15 |
| F18 | FastMCP internals encapsulation | 10 min | `server.py:46` | B14 |

**Total quick wins : ~3.5 heures**

---

## A — Port direct (pattern pur, pas de dépendance Cordis)

| # | Feature | Effort | dsh source | Fichiers Philum |
|---|---|---|---|---|
| A1 | Tool execution pipeline (pre/guard/around/post) | Gros | `core/tools/src/index.ts` (1946 lignes) | `server.py`, `tools.py`, `tools_write.py` |
| A2 | System prompt waterfall (sections ordonnées) | Moyen | `core/system-prompt/src/index.ts` (545 lignes) | `agent.py` |
| A3 | Goal system same-session | Moyen | `goal/goal/src/index.ts` (592 lignes) | `agent.py`, nouveau model DB |
| A4 | Skills filesystem (YAML frontmatter) | Moyen | `skill/skill-filesystem/src/index.ts` (1041 lignes) | Nouveau module |
| A5 | LLM multi-adapter waterfall | Moyen | `llm/llm/src/index.ts` (1026 lignes) | `agent_providers.py` |
| A6 | Token meter / context tracking | Moyen | `llm/token-meter/src/index.ts` (313 lignes) | `agent.py` |
| A7 | Web search providers multiples | Petit | `web/tool-web/src/index.ts` (95 lignes) | `tools.py` |
| A8 | User settings file provider | Moyen | `settings/src/index.ts` (899 lignes) | Nouveau module |
| A9 | Background jobs | Moyen | `jobs/src/index.ts` (179 lignes) | Nouveau module |
| A10 | Runtime invariants (chaque package) | Moyen | `packages/*/invariant.ts` | Chaque module |
| A11 | Scheduled tasks | Moyen | `schedule/src/index.ts` (77 lignes) | Nouveau module |
| A12 | Feedback on messages | Petit | `feedback/src/index.ts` (383 lignes) | `agent.py`, nouveau model |
| A13 | Attachment handling | Moyen | `attachment/src/` | `tools_write.py`, frontend |
| A14 | Session event sourcing | Gros | `core/session/src/index.ts` (1157 lignes) | `agent_sessions.py`, models |
| A15 | Context compaction améliorée | Moyen | `compaction/compaction-basic/src/index.ts` (431 lignes) | `agent.py` |
| A16 | Block assembler (streaming structuré) | Moyen | `llm/llm/src/assembler.ts` (207 lignes) | `agent.py`, `conversation.ts` |
| A17 | Credential layered resolution | Moyen | `credentials/src/index.ts` (323 lignes) | `agent_providers.py` |
| A18 | Approval timeout/auto-deny | Moyen | `interaction/user-approval/src/index.ts` (347 lignes) | `agent_approvals.py`, `ApprovalCard.svelte` |
| A19 | Agent instructions projection | Moyen | `context/agent-instructions/src/index.ts` (367 lignes) | `agent_workspace.py` |
| A20 | Time context dynamique | Petit | `context/time-context/src/index.ts` (209 lignes) | `agent.py` |
| A21 | File reference (@prefix) | Petit | `context/file-reference/src/index.ts` (63 lignes) | Frontend |
| A22 | Plan mode interactif | Moyen | `plan/src/` | `agent.py`, `agent_approvals.py` |
| A23 | Retry provider-routed | Moyen | `llm/llm-retry/src/index.ts` (226 lignes) | `agent.py` |
| A24 | SSE reconnection | Moyen | Non présent dans dsh (géré par UI) | `agent.ts`, `ChatPanel.svelte` |
| A25 | Permission system waterfall | Moyen | `interaction/user-approval/src/index.ts` | `agent_approvals.py` |

---

## B — Adaptation (concept bon, implémentation Cordis-dépendante)

| # | Feature | Effort | dsh source | Adaptation Philum |
|---|---|---|---|---|
| B1 | Scoped tool layers (isolation par agent) | Gros | `core/tools/src/index.ts` | Registry Python avec scopes |
| B2 | Session fork (création d'enfant) | Moyen | `core/session/src/index.ts` | Copy messages + new session |
| B3 | Subagent providers multiples | Gros | `subagent/` (8 packages) | Registry de providers avec ABC |
| B4 | Terminal PTY persistant | Gros | `terminal/tool-terminal/src/index.ts` | `asyncio.create_subprocess_exec` + PTY |
| B5 | LSP integration | Gros | `lsp/tool-lsp/src/index.ts` | `pygls` Python |
| B6 | Sandbox providers | Gros | `sandbox/` | `subprocess` avec restrictions |
| B7 | Workflow engine (scripts modèles) | Gros | `workflow/workflow-worker-thread/src/index.ts` | `exec()` + `threading.Thread` |
| B8 | Self-modification (cordis_define) | Très gros | `extensions/src/` | Pas pertinent pour Philum |
| B9 | Dual TypeScript faces | N/A | `tsconfig.host/client` | N/A — Philum est Python+Svelte |
| B10 | Cordis plugin composition | N/A | `vendor/cordis/` | N/A — Philum n'utilise pas de framework réactif |

---

## C — Inspiration (Philum a déjà une solution)

| # | Feature | dsh approach | Philum approach | Pourquoi garder Philum |
|---|---|---|---|---|
| C1 | Session persistence | JSONL + zstd | PostgreSQL | PG est plus robuste pour Philum |
| C2 | ICM 7 étapes | Workflow engine avec scripts | `agent_fiche.py` hardcoded | Plus simple, plus adapté au use case |
| C3 | SSE streaming | Pas de SSE (WebSocket) | SSE via FastAPI | SSE est plus simple pour Philum |
| C4 | Provider AES-GCM | Credentials layered | `agent_providers.py` | Encryption au repos est un plus |
| C5 | CSS tokens | `--dsw-*` variables | `app.css` tokens | Pattern similaire, pas besoin de changer |

---

## D — Hors périmètre

| # | Feature | Pourquoi |
|---|---|---|
| D1 | Cordis plugin framework | Framework TS, pas transposable à Python |
| D2 | React UI components | Philum utilise Svelte |
| D3 | VitePress docs | Philum a ses propres docs |
| D4 | Python SDK dsh | SDK pour dsh, pas pour Philum |
| D5 | E2B cloud sandbox | Trop heavy pour le MVP |
| D6 | OpenTelemetry | À considérer mais pas prioritaire |
| D7 | jscpd/oxlint/knip | Outils TS, pas pour Python |
| D8 | GitLab CI Python publish | Pas pertinent |
| D9 | Bundles dsh (web-app, headless) | Architecture Cordis |
| D10 | ACP (Agent Client Protocol) | Trop nouveau, pas de valeur MVP |

---

## Résumé par catégorie

| Catégorie | Nombre | Effort total estimé |
|---|---|---|
| **F — Quick win** | 18 | ~3.5 heures |
| **A — Port direct** | 25 | ~15 jours |
| **B — Adaptation** | 10 | ~20 jours |
| **C — Inspiration** | 5 | Documenter uniquement |
| **D — Hors périmètre** | 10 | Ignorer |
| **Total** | **68** | |

---

## Priorisation recommandée

### Sprint 1 — Quick wins (3.5h)
F1→F18 : tous les quick wins en une session.

### Sprint 2 — Fixes critiques (2 jours)
A16 (block assembler) → A6 (token meter) → A15 (compaction) → A2 (system prompt) → A23 (retry).

### Sprint 3 — Nouvelles capacités (1 semaine)
A3 (goal) → A4 (skills) → A14 (session event sourcing) → A9 (jobs) → A12 (feedback).

### Sprint 4 — UI/UX (3 jours)
A24 (SSE reconnection) → A21 (file reference) → A20 (time context) → A19 (instructions projection).

### Sprint 5 — Avancé (1 semaine)
B3 (subagents) → B4 (terminal PTY) → A17 (credentials) → A25 (permission waterfall).

---

_Faisabilité évaluée pour chaque item — 18 quick wins, 25 ports directs, 10 adaptations._
