# Phase 6 — Patterns défensifs

> Patterns qualité de dsh à porter dans Philum, avec priorité et effort estimé.

---

## 1. Registrations are effects (disposer)

**dsh** : Chaque `ctx.effect()` retourne un disposer. Quand le plugin est déchargé, tous les effets sont automatiquement nettoyés. Pas de fuite mémoire.

**Philum** : Pas de mécanisme de cleanup automatique. Les connexions DB, les tasks asyncio, les subscriptions ne sont pas toujours nettoyées.

**Recommandation** : Documenter comme dette technique. Pour les nouveaux modules (jobs, skills, goals), implémenter un `__aexit__` ou `cleanup()` method.

**Priorité** : Basse
**Effort** : Documentation uniquement

---

## 2. Model-visible equals logged

**dsh** : Tout ce qui atteint le modèle doit être reconstructible depuis le session log. Invariant vérifié par des runtime invariants.

**Philum** : `agent_sessions` stocke les messages role/content, mais pas les tool calls, pas les erreurs, pas les retries. Le log est incomplet.

**Recommandation** : Passer au session event sourcing (A14) pour avoir un log complet. Chaque action (tool call, error, retry, compaction) devrait être un event.

**Priorité** : Haute
**Effort** : 5 jours (A14)

---

## 3. Every package owns invariant.ts

**dsh** : Chaque package a un fichier `invariant.ts` qui vérifie les relations runtime au boot. Par exemple : "le tool registry ne contient pas de tools en double", "le session store a un seq contigu".

**Philum** : `_invariants.txt` = fichier statique listing les invariants. Pas de vérification runtime.

**Recommandation** : Créer `agent/invariants.py` avec des vérifications runtime :
- Pas de tools en double dans le registre MCP
- Chaque session a un seq contigu
- Les providers n'ont pas de clés corrompues
- Les quotas ne sont pas dépassés

**Priorité** : Haute
**Effort** : 1 jour

---

## 4. 100% per-file coverage gate

**dsh** : `vitest.config.ts` exige 100% de couverture par fichier. Pas de fichier sans test.

**Philum** : Tests existent mais pas de gate de couverture. Certains fichiers n'ont pas de tests.

**Recommandation** : Ajouter `--cov-fail-under=80` dans le CI. Augmenter progressivement vers 100%.

**Priorité** : Haute
**Effort** : 0.5 jour (config CI)

---

## 5. Focus management (dialogs)

**dsh** : `packages/interaction/` gère les dialogs avec focus trap, Escape, backdrop click. Pattern standard.

**Philum** : `ConsentementGratuit.svelte` n'a pas de focus trap, pas de Escape, pas de backdrop click.

**Recommandation** : Créer un composant `Dialog.svelte` réutilisable avec :
- Focus trap (Tab cycling)
- Escape key handler
- Backdrop click to close
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
- `tabindex="-1"` + auto-focus

**Priorité** : Haute
**Effort** : 0.5 jour

---

## 6. SQL → ripgrep/FTS

**dsh** : `packages/fs/tool-fs-search/` utilise ripgrep pour la recherche. Pas de SQL LIKE.

**Philum** : `search_my_excerpts` utilise `ILike` avec `%query%` — O(n) scan, injection possible.

**Recommandation** :
- Court terme : échapper les `%` et `_` (F11)
- Moyen terme : PostgreSQL FTS avec `tsvector`/`tsquery`
- Long terme : ripgrep pour la recherche fichier

**Priorité** : Haute (court terme), Moyenne (moyen terme)
**Effort** : 15 min (court terme), 2 jours (FTS)

---

## 7. Waterfall extension points

**dsh** : Chaque décision est un waterfall event que les plugins peuvent intercepter : `agent/pre-step`, `agent/turn-stopping`, `tools/pre-execute`, `llm/stream`, etc.

**Philum** : Code monolithique sans hooks d'extension. Pour ajouter un comportement, il faut modifier le code existant.

**Recommandation** : Pour les nouveaux modules, implémenter un pattern middleware simple :
```python
class MiddlewareChain:
    def __init__(self):
        self.middlewares = []
    
    async def execute(self, ctx, next):
        for mw in reversed(self.middlewares):
            next = partial(mw, ctx, next)
        await next()
```

**Priorité** : Moyenne
**Effort** : 1 jour (pour le framework) + adaptation des modules existants

---

## 8. Branded types

**dsh** : `Branded<B>` compile-time type safety pour les IDs. `SessionId`, `AgentId`, `TerminalSessionId` ne sont pas interchangeables.

**Philum** : UUIDs simples (`str`). Un `session_id` peut être passé là où un `agent_id` est attendu.

**Recommandation** : Utiliser `NewType` de Python :
```python
SessionId = NewType('SessionId', str)
AgentId = NewType('AgentId', str)
```

**Priorité** : Basse
**Effort** : 1 jour (refactor progressif)

---

## 9. Tests describe behavior

**dsh** : Les tests décrivent le comportement attendu, pas l'implémentation. `it('should reject stale revision', ...)`.

**Philum** : Tests existent mais certains testent l'implémentation plutôt que le comportement.

**Recommandation** : Adopter le pattern BDD : `describe('ToolRegistry') { it('should not allow duplicate tools', ...) }`.

**Priorité** : Basse
**Effort** : Continu

---

## 10. Exhaustive switch (assertNever)

**dsh** : Tous les `switch` sur des unions fermées se terminent par `assertNever(x)` pour détecter les cas non gérés au compile time.

**Philum** : Pas de switch exhaustif — les enums sont souvent gérés avec des `if/elif` sans catch-all.

**Recommandation** : Utiliser `match` avec pas de wildcard, ou `assert_never()` pour les enums.

**Priorité** : Basse
**Effort** : Continu

---

## 11. Contained fan-out

**dsh** : Quand un event a plusieurs listeners, chaque listener est appelé dans un try/except contenant. Un listener qui plante n'empêche pas les autres.

**Philum** : Les event handlers ne sont pas toujours contenus. Un handler qui plante peut crasher le tour.

**Recommandation** : Pour les nouveaux events (jobs, skills, goals), implémenter le pattern contained fan-out.

**Priorité** : Moyenne
**Effort** : 0.5 jour

---

## 12. Lossless JSON boundary

**dsh** : `snapshotJsonValue` à chaque frontière reject BigInt, functions, symbols, undefined, circular references.

**Philum** : `json.dumps/loads` — pas de validation de la structure.

**Recommandation** : Pour les events critiques (attestations, attestation payloads), ajouter une validation Pydantic avant persistence.

**Priorité** : Basse
**Effort** : 0.5 jour

---

## 13. Optimistic concurrency

**dsh** : `expectedRevision` sur les écritures settings. Si la revision ne matche pas → `SettingsConflictError`.

**Philum** : Pas de versioning sur les écritures. Risque de lost-update.

**Recommandation** : Ajouter un champ `version` sur les modèles critiques (`AgentCard`, `Source`, `SourceExcerpt`). Vérifier la version avant update.

**Priorité** : Moyenne
**Effort** : 2 jours (migration + refactor)

---

## 14. Secret redaction

**dsh** : `role('secret')` dans les schemas → stripped pour les wire surfaces.

**Philum** : Pas de redaction automatique des secrets dans les logs.

**Recommandation** : Ajouter un filter de logging qui masque les API keys et tokens.

**Priorité** : Haute (sécurité)
**Effort** : 0.5 jour

---

## Résumé

| Pattern | Priorité | Effort | Impact |
|---|---|---|---|
| Registrations are effects | Basse | Doc | Mémoire |
| Model-visible equals logged | Haute | 5j (A14) | Traçabilité |
| Runtime invariants | Haute | 1j | Fiabilité |
| 100% coverage gate | Haute | 0.5j | Qualité |
| Focus management | Haute | 0.5j | Accessibilité |
| SQL → FTS | Haute | 15min-2j | Sécurité + perf |
| Waterfall extensions | Moyenne | 1j | Extensibilité |
| Branded types | Basse | 1j | Type safety |
| Behavior tests | Basse | Continu | Qualité |
| Exhaustive switch | Basse | Continu | Fiabilité |
| Contained fan-out | Moyenne | 0.5j | Stabilité |
| Lossless JSON | Basse | 0.5j | Intégrité |
| Optimistic concurrency | Moyenne | 2j | Cohérence |
| Secret redaction | Haute | 0.5j | Sécurité |
| **Total** | | **~12 jours** | |

---

_14 patterns défensifs identifiés — 5 haute priorité, 4 moyenne, 5 basse._
