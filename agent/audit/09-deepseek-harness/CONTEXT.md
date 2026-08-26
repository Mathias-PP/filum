# 09 — Audit deepseek-harness → Philum

> Comparaison exhaustive du harness deepseek-harness (dsh) avec le harness Philum. Identification des bugs, imperfections, et solutions existantes dans dsh. Plans d'intégration prioritaires.

---

## Dashboard

| Phase | Statut | Fichier |
|---|---|---|
| Phase 1 — Inventaire croisé | ✅ Terminé | [`00-inventaire-croise.md`](./00-inventaire-croise.md) |
| Phase 2 — Bugs → solutions dsh | ✅ Terminé | [`01-bugs-vers-solutions.md`](./01-bugs-vers-solutions.md) |
| Phase 3 — Faisabilité | ✅ Terminé | [`02-faisabilite.md`](./02-faisabilite.md) |
| Phase 4 — Plans d'intégration | ✅ Terminé | [`03-plans-integration.md`](./03-plans-integration.md) |
| Phase 5 — Audit UI comparatif | ✅ Terminé | [`04-audit-ui-comparatif.md`](./04-audit-ui-comparatif.md) |
| Phase 6 — Patterns défensifs | ✅ Terminé | [`05-patterns-defensifs.md`](./05-patterns-defensifs.md) |

---

## Résumé exécutif

### Bugs critiques Philum identifiés

| # | Sévérité | Fichier | Bug |
|---|---|---|---|
| B1 | **Critical** | `agent_gratuit.py:340` | TOCTOU race — quota bypass non-atomique |
| B2 | **Critical** | `agent_approvals.py` | Approvals en mémoire perdues au restart |
| B3 | **Critical** | `agent_chat.py:343` | DB session lifetime mismatch dans le générateur SSE |
| B4 | **High** | `ChatPanel.svelte:870` | Race condition setTimeout(5000) reset enCours |
| B5 | **High** | `tools_write.py:1274` | SQL LIKE injection dans search_my_excerpts |
| B6 | **High** | `tools_write.py:797,1304` | datetime.now() sans UTC — timezone-dependent |
| B7 | **High** | `server.py:753` | rebuild_graph sans auth — vector DoS |
| B8 | **Medium** | `agent.py:911` | Pas de wall-clock timeout — boucle agent peut pendre indéfiniment |
| B9 | **Medium** | `ConsentementGratuit.svelte` | Pas de focus trap, Escape, backdrop click |
| B10 | **Medium** | `ChatPanel.svelte:816` | User messages sans break-words |
| B11 | **Medium** | `AgentMarkdown.svelte:56` | Code blocks sans max-h |
| B12 | **Medium** | `ToolCard.svelte:96` | JSON expandé sans max-h |
| B13 | **Medium** | `ApprovalCard.svelte` | Pas de timeout/auto-deny |
| B14 | **Medium** | `server.py:46` | Accès aux internals FastMCP — fragile |
| B15 | **Medium** | `agent_gratuit.py:107` | Provider transient avec UUID fake — risque de corruption DB |

### Capacités dsh transferables (top 10)

| # | Capacité dsh | Package | Gap Philum | Priorité |
|---|---|---|---|---|
| 1 | Tool pipeline pre/guard/around/post | `core/tools` | Pas de timeout, pas de validation pre-execute | Haute |
| 2 | Context compaction automatique | `compaction/compaction-basic` | Borne 48 tours en dur, pas de compaction par tokens | Haute |
| 3 | Goal system same-session | `goal` | Pas d'objectifs trackés | Haute |
| 4 | Skills filesystem (YAML frontmatter) | `skill/skill-filesystem` | Pas de système de skills | Haute |
| 5 | System prompt waterfall ordonné | `core/system-prompt` | Prompt fixe, pas de sections par plugin | Haute |
| 6 | Token meter / context tracking | `llm/token-meter` | Estimation `len(json)//4+8` très approximative | Haute |
| 7 | Subagent providers multiples | `subagent` (8 packages) | Modèle unique | Moyenne |
| 8 | Terminal PTY persistant | `terminal` | Bash one-shot uniquement | Moyenne |
| 9 | LLM multi-adapter waterfall | `llm/llm` | Cascade basique dans agent_gratuit | Moyenne |
| 10 | Approval timeout/auto-deny | `interaction` | Timeout fixe 5min, pas d'auto-deny | Moyenne |

### Patterns dsh à porter

| Pattern dsh | Philum actuel | Recommandation |
|---|---|---|
| Registrations are effects (disposer) | Pas de cleanup auto | Documenter dette technique |
| Model-visible equals logged | `agent_sessions` partiel | Renforcer traçabilité |
| Every package owns invariant.ts | `_invariants.txt` statique | **Porter** invariants runtime |
| 100% per-file coverage gate | Pas de gate couverture | **Ajouter** en CI |
| Focus management (dialogs) | Pas de focus trap | **Porter** depuis `interaction` |
| SQL → ripgrep/FTS | LIKE brut | **Porter** depuis `fs/tool-fs-search` |
| Waterfall extension points | Pas de waterfall | **Porter** pattern middleware |

---

## Structure

```
agent/audit/09-deepseek-harness/
├── CONTEXT.md                       # Ce fichier — dashboard
├── 00-inventaire-croise.md          # Phase 1 : matrice capability gap
├── 01-bugs-vers-solutions.md        # Phase 2 : mapping bugs → solutions dsh
├── 02-faisabilite.md                # Phase 3 : categorisation F/A/B/C/D
├── 03-plans-integration.md          # Phase 4 : plans détaillés
├── 04-audit-ui-comparatif.md        # Phase 5 : comparaison UI/UX
├── 05-patterns-defensifs.md         # Phase 6 : patterns qualité
└── preuves/
    └── *.md                         # Preuves de lecture
```

---

_Cet audit a été réalisé le 2026-08-26 en lisant l'intégralité du code dsh (55+ packages) et de Philum (agent backend + frontend)._
