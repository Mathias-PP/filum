# Plan d'exécution — Refonte UI/UX Filum

**Statut** : en cours d'exécution autonome
**Démarré** : 2026-05-15
**Branche base** : `main` (rebasée à jour)

Ce document est le contrat d'exécution agentique. À chaque session, lire d'abord la section « État courant » en bas du fichier, puis enchaîner sur la prochaine PR non démarrée.

---

## Décisions verrouillées (validées par l'utilisateur le 2026-05-15)

1. **Découpage en 6 PRs séquentielles** au lieu d'une PR géante. Chaque PR est mergeable indépendamment.
2. **Hero homepage** : option 1 (SVG + parallaxe CSS 3D, `perspective` + `rotate3d`, mouse tracking, anneaux orbitaux en rotation, étoiles scintillantes). Pas de Three.js pour le MVP.
3. **Lot 7.2 (fix édition sources)** sort en PR1 séparée, mergeable immédiatement.
4. **Dark mode** : maintenu (PR5).
5. **Source Serif 4** : confirmé, remplace Merriweather.
6. **Pas de branche backup `backup/ui-legacy`** : on tag `pre-redesign` sur main avant de démarrer.
7. **Composants UI Lot 2 essentiels** : Toast, Modal, Skeleton, EmptyState, ProgressSteps, ConfirmDialog. **Pas** Dropdown ni Tooltip (reportés).
8. **Lots 5 et 12 fusionnés** en une seule PR (« hero galaxie 3D »).
9. **`@tailwindcss/forms`** : ajouté avec audit des form elements existants pour éviter régression sur le formulaire sources.
10. **Svelte 5 runes** obligatoires sur tout nouveau composant (`$state`, `$derived`, `$props()`).

---

## Séquence des PRs

### PR1 — Fix édition sources + bouton retour dashboard (`fix/edit-sources-and-dashboard-link`)
**Petite, mergeable vite, débloque un bug réel.**

- [ ] Tag `pre-redesign` sur `main` (sauvegarde)
- [ ] Lot 7.2 : édition des sources existantes dans `routes/dashboard/new/[card_id]/sources/+page.svelte`
  - Bouton ✏️ « Modifier » sur chaque source
  - État `editingSourceId` + `editingSource`
  - Formulaire pré-rempli (format, category, author_kind, title, authors, annotation, is_pivot, parent_source_id) — pas l'URL
  - Submit appelle `api.sources.update(id, data)` en mode édition
  - Bouton « Annuler » revient au mode ajout
- [ ] Lot 4.2 / 8.1 : bouton « ← Tableau de bord » sur `routes/@[creator]/[card]/+page.svelte`
  - `{#if $currentUser?.username === creatorSlug}` uniquement
  - Placement : header de la fiche, à gauche du nom créateur
  - Style discret : `text-sm text-secondary` avec hover
- [ ] Tests : ajouter un test e2e ou unit minimal sur l'édition de source si la structure existante le permet
- [ ] Commit conventionnel `fix:` + `feat:`
- [ ] Push de la branche

### PR2 — Fondations design system + composants essentiels (`feat/design-system-foundations`)
- [ ] Lot 1 : design tokens CSS (palette `--bg-*`, `--text-*`, `--border*`, sémantiques)
- [ ] Lot 1 : `tailwind.config.js` (couleurs custom, Source Serif 4, borderRadius, plugin forms+typography)
- [ ] Lot 1 : `app.css` Google Fonts (Source Serif 4 remplace Merriweather, garde Inter)
- [ ] Lot 1 : grep `.btn|.card|.badge|.input` dans `src/` → migration ou conservation justifiée
- [ ] Lot 1 : `src/lib/components/index.ts` aligné (badges nouvelle taxonomie)
- [ ] Lot 2 : Button.svelte refondu (variants, tailles, Svelte 5 runes)
- [ ] Lot 2 : Card, Input, Alert, Avatar refondus
- [ ] Lot 2 : nouveaux composants Toast, Modal, Skeleton, EmptyState, ProgressSteps, ConfirmDialog
- [ ] Audit `@tailwindcss/forms` sur formulaire sources avant merge
- [ ] Commit unique squashable ou série courte

### PR3 — Hero galaxie 3D animé (`feat/hero-galaxy-3d`)
Lots 5 + 12 fusionnés.

- [ ] Remplacer "Vous" → "Filum" dans le SVG hero
- [ ] Wrapper hero `<div>` avec `perspective: 1200px`
- [ ] SVG container avec `transform: rotateX(...) rotateY(...)` lié à la position souris (Svelte action `mouseParallax`)
- [ ] Fond spatial : gradient `#0B0D17 → #1A1B2E` + 15-20 étoiles dispersées
- [ ] 2-3 anneaux orbitaux (`<ellipse>`) avec rotation lente CSS (`@keyframes spin`)
- [ ] Nœud central « Filum » avec halo pulsant + lueur radiale
- [ ] 6 nœuds sources sur orbites (décalés légèrement), couleurs `AUTHOR_COLORS` adaptées
- [ ] Liaisons centre→sources solides + arcs sources↔sources pointillés
- [ ] Animation scintillement sur 2-3 étoiles
- [ ] `prefers-reduced-motion` : désactive parallaxe + rotation + scintillement
- [ ] `role="img"` + `aria-label`
- [ ] Sections « Comment ça marche », « Pour qui », CTA : redesign DS
- [ ] IntersectionObserver reveal sur sections (fade + translateY)

### PR4 — Layout + dashboard + page publique (`feat/layout-dashboard-public`)
- [ ] Lot 4 : Header sticky `backdrop-blur`, menu mobile animé, dark mode toggle (stubbed pour PR5), avatar dropdown
- [ ] Lot 4 : Footer compact
- [ ] Lot 4.5 : page transitions Svelte (`{#key $page.url.pathname}` + `transition:fly`)
- [ ] Lot 7.1 : dashboard liste — stats compactes, cards avec hover actions, EmptyState, Skeleton, ConfirmDialog pour delete
- [ ] Lot 7.3 : création fiche step 1 avec ProgressSteps
- [ ] Lot 8.2 : page publique fiche — header éditorial, stats avec nouveaux compteurs (chercheur/media/institution_publique/individu), source list accordéon animé, 3 badges par source
- [ ] Lot 8.3 : graphe D3 — Skeleton placeholder, animation entrée nœuds en cascade, légende AUTHOR_COLORS

### PR5 — Dark mode complet (`feat/dark-mode`)
- [ ] CSS variables doubles (light + dark)
- [ ] Classe `.dark` sur `<html>` via store `theme.ts`
- [ ] Détection `prefers-color-scheme` + toggle manuel persistant (localStorage)
- [ ] Palette dark : `#0F0F11` / `#1A1A1E` / `#252529` / `#EDEDED` / `#9CA3AF`
- [ ] Adapter badges author-kind pour contraste dark (saturation +10-15%)
- [ ] Audit visuel de chaque page + composant
- [ ] Vérif WCAG AA contrastes dark
- [ ] Hero SVG : variante dark (déjà sombre par défaut, vérifier)
- [ ] Toggle dans header (icône Lucide sun/moon)
- [ ] Transition globale `transition-colors duration-300`

### PR6 — Pages info + animations + responsive + a11y (`feat/polish-and-a11y`)
- [ ] Lot 6 : about, features, roadmap (timeline), security, privacy — layout unifié, composants DS
- [ ] Lot 9 : micro-interactions (hover scale 1.02, focus-visible rings, prefers-reduced-motion partout)
- [ ] Lot 10 : responsive 320/375/768/1024/1440, mobile bottom sheets, graphe simplifié mobile
- [ ] Lot 11 : a11y — aria-label icônes, role alert toasts, aria-modal, aria-expanded menus, Escape fermeture, skip-to-content link

---

## Conventions d'exécution

- **Commits** : conventionnels, < 50 chars titre, corps optionnel en français
- **Tests** : passer `pnpm test` (frontend) + `pytest` (backend, si touché) avant chaque PR
- **Lint** : `pnpm lint` + `pnpm check` (svelte-check) doivent passer
- **Pas de `git push --force` sur main**. Force push seulement sur feature branch si rebase propre nécessaire
- **STATE.md mis à jour** à chaque PR mergeable (section « État production vérifié » + « Prochaines étapes »)
- **DECISIONS.md** : ADR par PR si décision technique non triviale (ex : ADR-020 design tokens, ADR-021 dark mode strategy)
- **Pas de modification de `.docs/00-09`** (specs verrouillées). Modifications uniquement dans `.docs/12-*`
- **Si bloqueur** : ne pas spéculer, instrumenter (cf. CLAUDE.md « Debug d'un bug prod »). Documenter dans la section « État courant » et passer à la PR suivante si possible

---

## État courant

**2026-05-15** — Plan rédigé. Démarrage PR1.

- [ ] PR1 — non démarrée
- [ ] PR2 — non démarrée
- [ ] PR3 — non démarrée
- [ ] PR4 — non démarrée
- [ ] PR5 — non démarrée
- [ ] PR6 — non démarrée

**Notes d'exécution** (à enrichir au fil des sessions) :
- _(vide)_
