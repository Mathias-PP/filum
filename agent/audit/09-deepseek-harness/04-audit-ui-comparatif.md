# Phase 5 — Audit UI/UX comparatif

> Comparaison détaillée des composants UI de dsh avec le frontend Philum. Patterns, accessibilité, responsive, states.

---

## 1. Architecture UI

| Aspect | dsh | Philum |
|---|---|---|
| **Framework** | React + CSS Modules | Svelte 5 + Tailwind CSS |
| **State management** | `useSession`, `useStore`, `useProjection` + stores partagés | 14 `$state` locaux + 5 `$derived` dans ChatPanel |
| **Composition** | Slot system via Cordis (`ctx.slots.register`) | Composants Svelte classiques |
| **Theming** | CSS custom properties `--dsw-*` | Tailwind design tokens dans `app.css` |
| **Modularité** | 45+ packages, chaque feature = un package | ~10 composants, ChatPanel = monolithe (1007 lignes) |

---

## 2. Comparaison par domaine

### Chat Conversation

| Aspect | dsh (`ui-conversation`) | Philum (`ChatPanel.svelte`) |
|---|---|---|
| **Architecture** | 20 fichiers : ChatView, MessageItem, AssistantMarkdown, skeletons, accessibility | 1 fichier monolithe (1007 lignes) |
| **Layout** | 3 phases : hero → active → settling. Sticky composer. 748px axis | Layout unique avec `h-[calc(100dvh-12rem)]` |
| **Scroll anchoring** | `document.elementsFromPoint()` + ResizeObserver | Scroll classique avec `scrollTo` |
| **Loading states** | TurnStatus avec shimmer + elapsed clock (15s) | Texte "En cours..." + LogoLoader |
| **Error states** | `TurnErrorRow` avec `StateDot` + error code | `<p>` avec `border-danger` — pas de role="alert" |
| **Empty states** | Hero shell avec suggestions | `<p>` + `<ul>` de boutons |
| **Streaming** | Structuré par event types | Concaténation brute de `message_delta` |

**Gaps Philum** :
- Pas de skeleton/shimmer pendant le chargement
- Pas de timestamp sur les messages
- Pas de "thinking" indicator
- Pas de branch/fork de conversation
- Pas de recherche dans la conversation
- Pas de copy-to-clipboard sur les messages

### Tool Call Rendering

| Aspect | dsh (`ui-tool`) | Philum (`ToolCard.svelte`) |
|---|---|---|
| **Architecture** | DisclosureRow + GenericToolCard + spécialisations (TerminalBlock, DiffBlock, etc.) | 1 composant (111 lignes) |
| **Spécialisation** | Chaque tool type a un rendu dédié | Tous les tools = même rendu JSON |
| **Loading** | ShimmerText animation | Texte "En cours..." |
| **Error** | `data-error` attribute + error summary | Texte rouge sous le header |
| **Expand/collapse** | Disclosure natif avec `aria-expanded` | Toggle custom sans aria |
| **Max height** | Hauteur bornée avec overflow | Pas de limite |
| **Copy** | Copie intégrée | Pas de copy |
| **Accessibility** | `role="status"`, `data-state`, `data-variant`, `data-tool` | Pas de role, pas de data attributes |

**Gaps Philum** :
- Pas de rendu spécial par tool type (diff pour edit, preview pour read, etc.)
- Pas de `aria-expanded` sur le toggle
- Pas de max-height sur les résultats
- Pas de copy button
- Pas de loading shimmer

### Approval System

| Aspect | dsh (`interaction`) | Philum (`ApprovalCard.svelte`) |
|---|---|---|
| **Architecture** | Service séparé avec waterfall, policy configurable | Composant inline dans le chat |
| **Timeout** | Configurable, auto-deny | 5 min fixe, pas d'auto-deny visuel |
| **Policy** | `ask` / `never` (auto-reject) | Toujours `ask` |
| **Authority** | Direct human vs subagent | Pas de distinction |
| **Audit** | `approval/asked` + `approval/decided` events | Pas d'audit |
| **Multiple pending** | Géré par le service | Chaque approval = un card dans le flux |
| **Accessibility** | `role="alertdialog"` (via service) | `<div>` inline — pas de role |

**Gaps Philum** :
- Pas de timeout visuel (countdown)
- Pas de policy configurable
- Pas d'audit trail
- Pas de `role="alertdialog"`
- Pas d'auto-scroll vers l'approval

### Settings/Configuration

| Aspect | dsh (`ui-settings-*`) | Philum |
|---|---|---|
| **Architecture** | 5 sous-packages : general, models, plugins, permissions, presets | Selectors inline dans ChatPanel |
| **Model config** | `ui-settings-models` avec provider editor, API key input, onboarding | Select dropdown dans le chat |
| **Permission config** | `ui-permission-presets` avec Menu dropdown | Rien de dédié |
| **Plugin management** | `ui-settings-plugins` avec inventory browser | Rien |
| **Conflict detection** | `expectedRevision` → SettingsConflictError | Pas de versioning |

**Gaps Philum** :
- Pas de page/settings dédiée
- La config modèle est mélangée au chat
- Pas de gestion des permissions
- Pas de gestion des plugins/tools

### Trajectory/Debug

| Aspect | dsh (`ui-trajectory`) | Philum |
|---|---|---|
| **Architecture** | 13 fichiers : timeline, table, search, snapshot | Rien |
| **Features** | Timeline visuelle, table ledger, recherche, pagination | Rien |
| **Accessibility** | `role="status"`, keyboard nav | Rien |

**Gap majeur** : Philum n'a aucune visibilité sur le parcours de l'agent. On ne peut pas voir quels tools ont été appelés, combien de tokens, combien de temps, etc.

### Plan/Goal

| Aspect | dsh (`ui-plan`, `ui-goal`) | Philum |
|---|---|---|
| **Plan** | Chip inline avec exit action | `MODE_PLAN` = instruction system prompt |
| **Goal** | Docked strip avec glyph, phase label, edit mode | Rien |
| **Accessibility** | `aria-label`, `role="alert"`, tooltips | Rien |

**Gap** : Pas de visualisation des objectifs ni du plan en cours.

---

## 3. Accessibilité — matrice comparative

| Critère | dsh | Philum | Score |
|---|---|---|---|
| ARIA roles | `status`, `alert`, `listbox`, `option`, `tree`, `treeitem`, `tablist`, `tab` | `log`, `dialog`, `alert` (toasts) | dsh 9 / Philum 3 |
| ARIA attributes | `aria-label`, `aria-expanded`, `aria-selected`, `aria-pressed`, `aria-haspopup`, `aria-current`, `aria-busy`, `aria-disabled`, `aria-live`, `aria-activedescendant`, `aria-level` | `aria-label` (textarea), `aria-live` (log), `aria-hidden` (decoratif) | dsh 11 / Philum 3 |
| Keyboard | Arrow keys, Enter/Space, Escape, Home/End, Tab trap | Enter/Shift+Enter, Escape (non implémenté) | dsh 5 / Philum 1 |
| Focus management | `preventScroll`, `revealCaret`, `keepFocus`, `autoFocus`, `queueMicrotask` | Rien de dédié | dsh 5 / Philum 0 |
| Focus indicators | `focus-visible` avec brand-primary color | `focus:ring` Tailwind (partiel) | dsh 5 / Philum 2 |
| Reduced motion | `prefers-reduced-motion` partout | Cursor uniquement | dsh 5 / Philum 1 |
| Screen reader | `visuallyHidden` pour états color-only | Rien de dédié | dsh 2 / Philum 0 |
| **Total** | **42** | **10** | **dsh 4× plus accessible** |

---

## 4. Responsive — matrice comparative

| Critère | dsh | Philum |
|---|---|---|
| Container queries | `container-type: inline-size` partout | Pas de container queries |
| Breakpoints | `@media (max-width: 760px)`, `@media (max-width: 560px)`, `@container (max-width: 620px)` | Pas de breakpoints explicites |
| Fluid sizing | `max-width: min(calc(...), 100%)`, `max(180px, 1fr)` grids | `dvh` units, `flex-wrap` |
| Touch | `touch-action: none` sur drag handles | Pas de `touch-action` |
| Scrollbar | `scrollbar-gutter: stable` | Pas de gestion |
| Mobile chat | Adapter card width, collapse columns | `px-1` trop serré |

**Score** : dsh 6 / Philum 2

---

## 5. States — matrice comparative

| State | dsh | Philum |
|---|---|---|
| Loading | Shimmer, spinner, `aria-busy`, disabled controls | Texte "En cours...", LogoLoader |
| Error | `role="alert"`, retry button, error code, Toast | `<p class="text-danger">`, pas de retry |
| Empty | Skeleton, placeholder, dashed borders | `<p>` + boutons |
| Streaming | Structuré par event types, elapsed clock | Concaténation brute |
| Success | StateDot, completion indicator | Rien de dédié |

**Score** : dsh 5 / Philum 2

---

## 6. Recommandations UI/UX prioritaires

### Immédiat (Quick wins)
1. Ajouter `role="alert"` sur les erreurs + retry button
2. Ajouter `aria-busy` pendant le streaming
3. Ajouter `aria-expanded` sur ToolCard toggle
4. Ajouter `max-h` sur code blocks et ToolCard JSON
5. Focus trap + Escape sur ConsentementGratuit

### Court terme (1-2 semaines)
6. Skeleton/shimmer pendant le chargement initial
7. Timestamp sur les messages
8. Copy-to-clipboard sur les messages et code blocks
9. Error retry button
10. Approval countdown timer

### Moyen terme (1 mois)
11. Refactor ChatPanel en composants modulaires
12. Tool rendering spécialisé par type
13. Trajectory view (tool calls, tokens, timing)
14. Settings page dédiée
15. SSE reconnection

### Long terme (3 mois)
16. Goal visualization
17. Plan mode interactif
18. Command palette
19. Skill browser
20. Subagent management

---

_Audit UI/UX comparatif — dsh 4× plus accessible, 3× plus responsive, 2.5× plus riche en states._
