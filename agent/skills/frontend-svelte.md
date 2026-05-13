# Skill: Frontend SvelteKit

> Quand l'utiliser : composant Svelte, route, store, SSR, D3, design system.

## Contexte

Le frontend est en SvelteKit 2 + Svelte 5 + TS strict + Tailwind. SSR est **off par défaut** (CSR pour le dashboard), réactivé route par route via `+page.ts` pour les pages publiques. Plusieurs pièges spécifiques à Svelte 5 et D3 ont déjà été payés.

## Checklist d'exécution

### Pour un nouveau composant

1. Créer dans `apps/frontend/src/lib/components/` en **kebab-case** (ex: `source-card.svelte`).
2. TypeScript strict : props typées via `interface Props { ... }` + `let { ... }: Props = $props()`.
3. Réactivité : `$state`, `$derived`, `$effect` (Svelte 5). **Pas** de `let` réactif implicite (Svelte 4 style).
4. Style : Tailwind. Si CSS custom, dans un `<style>` scopé (Svelte le scope par défaut).
5. Accessibilité : pas de `<aside role="dialog">`, utiliser `<div role="dialog" aria-modal="true">`.

### Pour une nouvelle route

1. Créer dans `apps/frontend/src/routes/` selon convention SvelteKit.
2. Si la route est **publique** (SEO/GEO critique) : créer un `+page.ts` avec `export const ssr = true`. Sinon, hérite du `+layout.ts` parent (SSR off).
3. Si la route utilise un composant D3 (ou tout code touchant `window`/`document`) : **dynamic-import côté client** :
   ```typescript
   onMount(async () => {
     const { default: SourceGraph } = await import('$lib/components/SourceGraph.svelte');
     // ...
   });
   ```
4. Auth guard (jalon M2 pour `/dashboard*`) : `+layout.ts` qui vérifie le store `auth` et `throw redirect(302, '/')` si non connecté. Côté SSR, faire un `fetch('/api/v1/auth/me', { credentials: 'include' })` dans le load.

### Pour D3

1. Importer depuis `'d3'` (umbrella). **Jamais** depuis `'d3-force'`, `'d3-selection'`, etc.
2. Typer explicitement : `.selectAll<SVGGElement, MyType>('g')` avant `.data().join()`.
3. `.style('display', flag ? '' : 'none')` — string vide, jamais `null`.
4. ResizeObserver pour adapter au container — pattern dans `SourceGraph.svelte`.

### Couleurs des types de source

- Source unique de vérité : `apps/frontend/src/lib/utils/source-colors.ts`.
- Réutiliser cette fonction dans tout composant qui affiche un type de source (graphe, badge, liste). Ne pas hardcoder.

### Vérifications avant commit

```bash
cd apps/frontend
pnpm install --frozen-lockfile     # doit exit 0
pnpm run check                     # type check
pnpm run lint                      # eslint
pnpm run test                      # vitest
pnpm run build                     # vite build
```

## Pièges spécifiques

- **pnpm 11** : ne pas upgrade. Cf. `PITFALLS.md` 2.1 + ADR-013.
- **D3 sub-imports** : casse les types. Cf. `PITFALLS.md` 2.2.
- **`.style('display', null)`** : casse le build TS. Cf. `PITFALLS.md` 2.3.
- **SSR oublié sur route publique** : page invisible aux bots. Cf. `PITFALLS.md` 2.4.
- **`tsconfig.json` qui redéclare `paths`** : casse `$lib`. Cf. `PITFALLS.md` 2.5.
- **`toLocaleDateString({timeStyle})`** : utiliser `toLocaleString`. Cf. `PITFALLS.md` 2.6.
- **`$page.params.X` typé `string | undefined`** : `?? ''`. Cf. `PITFALLS.md` 2.7.
- **`<aside role="dialog">`** : utiliser `<div role="dialog" aria-modal="true">`. Cf. `PITFALLS.md` 2.8.

## Fichiers à connaître

- `apps/frontend/svelte.config.js` — alias (`kit.alias`), pas de `kit.vitePlugin.inspector` (supprimé SvelteKit 2)
- `apps/frontend/vite.config.ts`
- `apps/frontend/src/app.html`, `src/app.css`
- `apps/frontend/src/routes/+layout.ts` — `ssr = false` par défaut
- `apps/frontend/src/lib/api/` — client API typé, `PUBLIC_API_BASE_URL` env
- `apps/frontend/src/lib/stores/` — auth, cards
- `apps/frontend/src/lib/components/SourceGraph.svelte` — exemple D3 complet
- `apps/frontend/src/lib/utils/source-colors.ts` — single source of truth couleurs

## Pour aller plus loin

- ADR-013 (pnpm 10 pinned)
- ADR-016 (graphe D3 + `parent_source_id`)
- ADR-017 (SSR sélectif, JSON-LD)
- `.docs/05-design-system.md` (palette, typo, composants)
