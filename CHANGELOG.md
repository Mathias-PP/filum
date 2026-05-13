# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Itération 3] — 2026-05-13

### Added
- **Extracteur URL** (`app/extractors/url_extractor.py`) : Crossref pour les DOIs (titre, auteurs, date, citations), HTML scraping (og:title, og:description, author, date) en fallback
- **Endpoint `GET /api/v1/sources/extract`** : métadonnées best-effort sans auth, paramètre `url` validé `HttpUrl` (guard SSRF)
- **Dashboard création de fiche** : 2 routes SvelteKit — `/dashboard/new` (étape 1 : titre, slug, description, URL, plateforme, type) et `/dashboard/new/[card_id]/sources` (étape 2 : ajout/suppression sources + publication)
- **Test vitest `source-colors.test.ts`** : vérifie que les 6 `SourceType` ont des couleurs hex valides (label, fill, stroke, text, bgClass)
- Deps backend : `beautifulsoup4>=4.12.0`, `lxml>=5.0.0`
- Deps frontend : `@eslint/js`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `eslint-config-prettier`, `eslint-plugin-svelte`, `svelte-eslint-parser`

### Changed
- **CI enforced** : supprimé `|| true` et `continue-on-error` sur les steps lint/prettier frontend — ESLint et Prettier désormais bloquants
- **CI `test-frontend`** : ajout `pnpm exec svelte-kit sync` avant `pnpm run test` (`.svelte-kit/tsconfig.json` absent en checkout propre)
- **ESLint** : réécriture en flat config ESLint 9 (`eslint.config.js`), suppression de `.eslintrc.cjs`
- **`crypto/signing.py`** : `Canonicalizer` et `SigningService` déplacés hors de `hashing.py` (qui ne garde que `HashService`)
- **Wayback background task** : session SQLAlchemy isolée (`async_session_maker()` dans `_archive_bg`) — évite `MissingGreenlet`

### Fixed
- 57 erreurs ESLint : browser globals (`no-undef: off` pour Svelte), `state_referenced_locally` (composants Avatar, Button, Input, SourceGraph convertis à `$derived()`), unused imports dans dashboard et stores
- DOI regex trop greedy : `(.+)` → `([^\s?#]+)`
- Suppression dead code `_openalex_impact` (bug logique : retournait toujours `None`, jamais appelée)

---

## [Unreleased]

### Added
- **Embranchement en Y** dans le graphe interactif : quand deux sources du même auteur citent le même parent, un nœud de jonction est créé automatiquement (arêtes Nœud central → Léa Marchand → 2 notes de tournage)
- **Source YouTube** Artem Kirsanov sur la neuroscience de la mémoire (seed demo)
- **Types de source** `video` (Documentaire→Vidéo) et `image` (Illustration→Image)

### Changed
- **Logo** : 6 branches dédoublées en 12 (embranchement en Y), suppression des lignes pointillées d'arrière-plan
- **Graphe interactif** : étiquette « Vidéo » supprimée du nœud central, créateur centré au-dessus du nœud (zoom ≥ 0.7), titre au-dessus du créateur (zoom ≥ 1.5)
- **Labels types source** : Peer-reviewed→Article scientifique, Original→Contenu original, Documentaire→Vidéo, Illustration→Image
- **Conflits d'intérêt** : rouge→ambré, icône ⚠ supprimée, badge conservé sans alarme
- **En-tête fiche publique** : layout compact (avatar + créateur + titre sur une ligne, description en sous-titre), hauteur du graphe augmentée (68vh→75vh)
- **Page d'accueil** : nouveau tagline « Vous allez adorer partager vos références », correction « bibliography »→« bibliographie »
- **Démo** : 18 sources (au lieu de 16), 8 arêtes de citation, ajout vidéo YouTube
- **CI/CD** : `@sveltejs/vite-plugin-svelte` ^5→^6, `vitest` ^2→^3 (résout le crash Test Frontend, compatible vite@6)

### Removed
- Badge vérifié (coche bleue) sur l'avatar de la fiche publique
- Panneaux conflit d'intérêt expansés (gros bloc rouge) — le badge textuel ambré reste

### Fixed
- **Fork Y sans nœud visible** : le nœud de jonction est désormais invisible (radius 0, transparent) et repositionné chaque frame au point d'embranchement idéal (40px du parent sur la ligne vers le centre de gravité des enfants). Résultat : un trait qui se divise en deux sans point intermédiaire visible.
- **Y-branching réel** : les deux sources Nader avaient des chaînes `authors` différentes → pas de groupement. Remplacées par deux sources **Léa Marchand** (notes de tournage + compte-rendu), toutes deux en premier cercle (`parent_index: None`), même auteur exact → Y-branch fonctionnel entre le nœud central et les deux sources.
- Bug link direction dans le code Y-branch : `links.findIndex` ne matchait pas les liens de premier cercle (`kind: 'card'` → `source: cardId, target: sourceId`). Corrigé en vérifiant les deux directions.
- Crash Test Frontend : incompatibilité vite-plugin-svelte@6 + vitest@2 (utilisait vite@5). Résolu en montant vitest@3 (vite@6).
- Typo homepage : « bibliography » → « bibliographie »
- STATE.md + CHANGELOG.md mis à jour avec toutes les modifications

---

## [Pré-MVP — base scaffolding] — 2026-04 → 2026-05-11

État initial avant la session de merge et déploiement du 2026-05-12.

### Added
- Specs initiales du projet (`.docs/`)
- Manifeste fondateur, maquettes, choix de stack
- Backend FastAPI : models, schemas, services, routes
- Frontend SvelteKit : design system, stores, routes
- Conftest avec fixtures async DB (SQLite + aiosqlite)
- Tests unitaires AuthService (15 tests : JWT, cookie/bearer, expired, soft-delete, Google OAuth)
- CI/CD scaffolding (8 jobs GitHub Actions)
- dbt project sur DuckDB
- Alembic migration initiale (001_initial)

### Changed
- `case_sensitive=True` dans pydantic-settings → toutes les variables d'environnement en lowercase (ADR-010)

---

*Pour ajouter une release, copier le template :*

<!--
## [X.Y.Z] — Titre court

**Date** : YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...
-->
