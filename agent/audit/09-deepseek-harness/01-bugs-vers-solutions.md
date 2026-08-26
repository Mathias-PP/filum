# Phase 2 — Mapping bugs Philum → solutions dsh

> Pour chaque bug/imperfection identifié dans Philum, la solution existante dans deepseek-harness.

---

## Bugs critiques

### B1 — TOCTOU race : quota bypass non-atomique

**Philum** : `agent_gratuit.py:340-364` — SELECT then UPDATE sur `messages_used`. Deux requêtes concurrentes peuvent toutes deux passer le check et dépasser le quota.

**dsh** : Pas de quota similaire — dsh n'a pas de free tier avec compteur. Mais le pattern est dans `packages/session/` : les mutations sont append-only au log, pas des UPDATE en place. L'état est dérivé du log, pas d'un compteur en DB.

**Solution Philum** : Utiliser `UPDATE ... SET messages_used = messages_used + 1 WHERE messages_used < quota RETURNING messages_used` (atomic upsert PostgreSQL). Ou passer à un event-sourced counter comme dsh.

---

### B2 — Approvals en mémoire perdues au restart

**Philum** : `agent_approvals.py` — dict Python `{request_id: Future}`. Si le process crash, les Futures sont perdues et les agents boucles meurent silencieusement.

**dsh** : `packages/interaction/` — approvals enregistrés dans le session event log (`approval/asked` + `approval/decided`). Le log est persisté en JSONL. Au restart, les approvals en attente sont reconstituées depuis le log.

**Solution Philum** : Persister les approvals en attente dans la DB (`AgentSession` ou table dédiée) avec un TTL. Au restart, reconstituer les Futures depuis les approvals non résolues.

---

### B3 — DB session lifetime mismatch dans SSE

**Philum** : `agent_chat.py:343-349` — `_persister_tour` est appelé après le yield loop, mais la DB session FastAPI peut déjà être fermée par le middleware.

**dsh** : Pas de DB dependency injection — la persistence est gérée par le session store (`packages/session/session-persistence-jsonl/`) qui est un service séparé avec sa propre lifecycle. Le session log est persisté à chaque event, pas à la fin du tour.

**Solution Philum** : Créer une session DB dédiée pour la persistence SSE, indépendante de la session FastAPI. Ou persistant les messages au fur et à mesure (à chaque `ajouter_message`) plutôt qu'à la fin du tour.

---

## Bugs high

### B4 — Race condition setTimeout(5000)

**Philum** : `ChatPanel.svelte:870` — `setTimeout(() => (enCours = false), 5000)` reset le flag pendant que la requête est encore en vol.

**dsh** : `packages/core/agent-loop/src/agent.ts` — l'état `enCours` (ou `phase`) est dérivé du session event log, pas d'un timer. La phase `running` est terminée quand le dernier event du tour est commité, pas quand un timer expire.

**Solution Philum** : Remplacer le setTimeout par un tracking du cycle de vie de la requête. `enCours` devrait être réinitialisé quand le dernier event SSE du tour est reçu (`done` ou `error`), pas après un délai fixe.

---

### B5 — SQL LIKE injection

**Philum** : `tools_write.py:1274` — `SourceExcerpt.text.ilike(f"%{q}%")` sans échappement des `%` et `_`.

**dsh** : `packages/fs/tool-fs-search/` — utilise ripgrep (`@vscode/ripgrep`) pour la recherche. Pas de SQL LIKE. La recherche full-text est externalisée vers un outil spécialisé.

**Solution Philum** : (1) Échapper les `%` et `_` dans la requête : `q.replace('%', '\\%').replace('_', '\\_')`. (2) Ou mieux : migrer vers PostgreSQL `ILIKE` avec `ESCAPE '\\'`. (3) À long terme : FTS (Full-Text Search) PostgreSQL.

---

### B6 — datetime.now() sans UTC

**Philum** : `tools_write.py:797,1304` — `datetime.now().replace(tzinfo=None)` au lieu de `datetime.now(UTC).replace(tzinfo=None)`.

**dsh** : `packages/core/session/src/index.ts` — `Date.now()` partout (UTC par défaut en JS). Pas de problème de timezone.

**Solution Philum** : Utiliser `datetime.now(UTC).replace(tzinfo=None)` partout. Créer une utilitaire `utcnow_naive()` pour éviter la duplication.

---

### B7 — rebuild_graph sans auth

**Philum** : `server.py:753` — `rebuild_graph()` n'a pas de requirement d'authentification.

**dsh** : Tous les tools dsh ont une autorisation gérée par le pipeline `tools/pre-execute`. Chaque tool peut déclarer un guard qui vérifie les permissions.

**Solution Philum** : Ajouter `exiger_utilisateur` sur `rebuild_graph`. Ou mieux : le rendre sensible et l'ajouter à `est_sensible()`.

---

## Bugs medium

### B8 — Pas de wall-clock timeout

**Philum** : `agent.py:911` — la boucle `boucle()` n'a pas de timeout global. Si un provider ne répond jamais, la boucle tourne indéfiniment.

**dsh** : `packages/core/agent-loop/src/agent.ts` — AbortController par phase avec `signal.throwIfAborted()` à chaque point de synchronisation. Timeout configurable par tool.

**Solution Philum** : Ajouter un timeout global sur `boucle()` : `asyncio.wait_for(boucle(...), timeout=TEMPS_MAX Tours)`. Utiliser `asyncio.CancelledError` pour la cancellation propre.

---

### B9 — Modal sans focus trap

**Philum** : `ConsentementGratuit.svelte` — pas de focus trap, pas de Escape, pas de backdrop click.

**dsh** : `packages/interaction/` — le permission system gère les dialogs avec focus management. `ui-commands` a un focus trap avec `capture-phase pointerdown` pour dismiss.

**Solution Philum** : Implémenter un focus trap basique : (1) `tabindex="-1"` + `autoFocus` sur le dialog, (2) piège Tab dans le dialog, (3) Escape pour fermer, (4) backdrop click pour fermer.

---

### B10 — User messages sans break-words

**Philum** : `ChatPanel.svelte:816` — les messages user n'ont pas `break-words`/`overflow-wrap`.

**dsh** : `ui-conversation` — `max-width: min(525px, 82%)` sur les bubbles user + `overflow-wrap: break-word` dans le CSS global.

**Solution Philum** : Ajouter `break-words` sur le div du message user.

---

### B11 — Code blocks sans max-h

**Philum** : `AgentMarkdown.svelte:56` — `<pre>` sans `max-h`.

**dsh** : `ui-tool` — les blocs de code ont `max-height` avec `overflow-y: auto` et un threshold de 20 lignes.

**Solution Philum** : Ajouter `max-h-[60vh] overflow-y-auto` sur `<pre>`.

---

### B12 — JSON expandé sans max-h

**Philum** : `ToolCard.svelte:96` — `<pre>` expandé sans limite de hauteur.

**dsh** : `ui-tool` — les résultats tools ont un truncation configurable et un expand/collapse avec hauteur bornée.

**Solution Philum** : Ajouter `max-h-[50vh] overflow-y-auto` sur le `<pre>` expandé. Ou tronquer au-delà de N lignes avec "Voir plus".

---

### B13 — Approvals sans timeout

**Philum** : `ApprovalCard.svelte` — pas de timeout/auto-deny. L'approval reste en attente indéfiniment.

**dsh** : `packages/interaction/` — le permission system a un timeout configurable. `user-approval` : `policy` can be `'never'` (auto-reject).

**Solution Philum** : Ajouter un timeout visuel (countdown) + auto-deny après 5 minutes (configurable). Afficher un warning avant auto-deny.

---

### B14 — Accès aux internals FastMCP

**Philum** : `server.py:46` — `mcp._local_provider._components` accède aux internals de FastMCP.

**dsh** : Pas de dépendance à des internals — tous les services sont des Cordis plugins avec interface publique.

**Solution Philum** : encapsuler l'accès dans une fonction utilitaire avec un try/except qui donne un message d'erreur clair si FastMCP change son API interne.

---

### B15 — Provider transient avec UUID fake

**Philum** : `agent_gratuit.py:107-116` — crée un `AgentProvider` avec `uuid.uuid4()` comme ID et `uuid.UUID(int=0)` comme `creator_id`. Si `db.add()` est appelé accidentellement, cela corrompt la DB.

**dsh** : Les providers transient sont des objets in-memory, jamais persistés. `packages/llm/llm/src/index.ts` : les adapter registrations sont des effets Cordis avec disposer automatique.

**Solution Philum** : Ajouter un flag `transient=True` sur le provider et un guard dans le model SQLAlchemy qui empêche `db.add()` sur les providers transient. Ou créer une classe séparée `TransientProvider` qui n'est pas un modèle DB.

---

## Bugs low

### B16 — aria-busy manquant

**dsh** : `ui-conversation` — utilise `aria-busy` dynamique pendant le streaming.

**Solution** : Ajouter `aria-busy={enCours}` sur le container de conversation.

---

### B17 — aria-expanded manquant

**dsh** : `ui-tool` — `aria-expanded` sur chaque toggle expand/collapse.

**Solution** : Ajouter `aria-expanded={ouvert}` sur le bouton toggle de ToolCard.

---

### B18 — LogoLoader flicker

**dsh** : Les events sont typés (`assistant/chunk`, `assistant/message`, `tool/call`). Pas de flicker car chaque phase a un event distinct.

**Solution Philum** : Séparer l'état "en attente de tokens" de l'état "tool calls en cours" dans le reducer conversation.ts.

---

### B19 — DB session pas séparée

**dsh** : Session store = service séparé (`packages/session/`). Pas de DB partagée.

**Solution Philum** : Créer un `AsyncSession` dédié pour la persistence SSE, avec sa propre lifecycle.

---

### B20 — Color inconsistency

**dsh** : `ui-theme` — tokens CSS uniques (`--dsw-alias-state-business-primary`).

**Solution Philum** : Remplacer `text-blue-600` par `text-info` dans `+error.svelte`.

---

## Résumé

| Sévérité | Nombre | Solutions dsh disponibles |
|---|---|---|
| Critical | 3 | 3 (event sourcing, atomic ops, separate session) |
| High | 4 | 4 (request lifecycle, FTS, UTC util, auth pipeline) |
| Medium | 7 | 7 (timeout, focus trap, max-h, truncation, etc.) |
| Low | 5 | 5 (aria, theme, typing) |
| **Total** | **19** | **19** |

---

Mapping complet bugs → solutions — 19 bugs, 19 solutions identifiées.
