# `apps/frontend` — SvelteKit + Tailwind

Le site public Philum (`https://filum-eight.vercel.app`) et le dashboard créateur. SvelteKit 2 + Svelte 5 runes + TypeScript strict + Tailwind CSS. Pas de framework UI lourd : composants Svelte custom.

## Ce que ça fait, en une phrase

Rend les fiches publiques (`/@creator/card`), les exports (`.md`, `.philum.json`), la page découverte, les pages créateur (dashboard, wizard, corbeille), le feed, l'authentification Google, et la sandbox de design.

## Comment le lancer en local

```bash
cd apps/frontend
pnpm install --frozen-lockfile   # pnpm 10.33.4 pinned via packageManager
pnpm run dev                     # http://localhost:5173
```

Tests, lint, check :

```bash
pnpm test                        # vitest
pnpm run check                   # svelte-check + tsc
pnpm run lint                    # eslint + prettier --check
pnpm run format                  # prettier --write
pnpm run generate:api            # régénère src/lib/api/generated.ts depuis openapi.json
```

Le proxy `/api/[...path]` (voir `src/routes/api/[...path]/+server.ts`) proxifie vers le backend pour éviter les cookies tiers (cf. ADR sur Vercel↔backend et ITP Safari, `agent/PITFALLS.md` §3).

## Où vivent les choses

| Sous-dossier          | Rôle                                                                                                                                                                                                                                                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/routes/`         | Routes SvelteKit. Publiques : `/`, `/about`, `/discover`, `/features`, `/feed`, `/@[creator]`, `/@[creator]/[card]`, `/c/[creator]/[card]` (URL agent-friendly sans `@`), `/developers`, `/roadmap`, `/privacy`, `/sandbox`. Créateur : `/dashboard`, `/dashboard/new`, `/dashboard/new/[card_id]/sources`, `/dashboard/recherche` |
| `src/lib/components/` | Composants Svelte partagés (`Avatar`, `SourceGraph`, `HeroPulsar`, `Logo`, `ConfirmDialog`, `Toast`, `Modal`, etc.)                                                                                                                                                                                                                |
| `src/lib/stores/`     | Stores Svelte (`currentUser`, etc.)                                                                                                                                                                                                                                                                                                |
| `src/lib/api/`        | Client API typé, `generated.ts` produit par `openapi-typescript` depuis `../backend/openapi.json`                                                                                                                                                                                                                                  |
| `src/lib/utils/`      | Utilitaires purs (`citation-meta`, `coins`, `reveal`, etc.)                                                                                                                                                                                                                                                                        |
| `src/lib/actions/`    | Actions Svelte (`reveal` pour l'apparition au scroll)                                                                                                                                                                                                                                                                              |
| `src/hooks.server.ts` | Réécriture MIME sur les URLs `.md` et `.philum.json`                                                                                                                                                                                                                                                                               |
| `src/tests/`          | Tests vitest (`citation-meta.test.ts`, `coins.test.ts`)                                                                                                                                                                                                                                                                            |
| `static/`             | Assets statiques servis à la racine                                                                                                                                                                                                                                                                                                |

## SSR et hydration

`+layout.ts` est `ssr = false` par défaut. Surcharger via `+page.ts` (`export const ssr = true`) sur les routes publiques qui en ont besoin (fiche publique, découverte, profil). Les composants qui utilisent `document`/`window` (D3) sont dynamic-imported côté client.

## Design system

Tokens `ink-*`/`surface-*`/`border`/`danger`/`info` en clair et sombre (`dark:`). Palette et typographie dans `.docs/05-design-system.md`. Toute nouvelle page doit utiliser les tokens et respecter les composants de base — pas de couleurs `bg-white`/`slate-*` codées en dur (leçon PR de mai 2026 : illisibles en dark mode).

## Déploiement

Vercel auto-deploy sur push `main`. Preview URL par PR. Config projet Vercel : voir dashboard (aucun secret sensible côté frontend).

## Références

- Règles techniques stables : [`../../agent/references/CODING_GUIDE.md`](../../agent/references/CODING_GUIDE.md)
- Pièges frontend/D3/Svelte : [`../../agent/PITFALLS.md`](../../agent/PITFALLS.md) §2
- Skill Svelte : [`../../agent/skills/frontend-svelte.md`](../../agent/skills/frontend-svelte.md)
- Design system : [`../../.docs/05-design-system.md`](../../.docs/05-design-system.md)
