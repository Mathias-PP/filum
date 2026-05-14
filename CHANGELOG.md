# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased] — publish diagnostics + safety net (PR #34, 2026-05-14)

### Added
- **`GET /health`** retourne désormais `commit` : SHA git de la version déployée (`RAILWAY_GIT_COMMIT_SHA` exposé par Railway). Permet de vérifier en un `curl` que Railway a bien redéployé le dernier commit. Comparer à `git log -1 --format=%H origin/main`.

### Changed
- **`POST /cards/{id}/publish`** : enveloppé d'un `try/except Exception` qui log la stack côté serveur et retourne un 500 JSON propre `{"error": {"code": "publish_failed", "message": "..."}}` au lieu de laisser n'importe quelle exception tuer la connexion ASGI (ce qui faisait que le navigateur voyait `Failed to fetch`, indistinguable d'une coupure réseau).
- **Frontend publish error** (`sources/+page.svelte`) : ne plus afficher « Impossible de contacter le serveur » sur `TypeError: Failed to fetch` — pointer l'utilisateur vers la console DevTools (onglet Network) avec le statut HTTP réel. Log brut dans `console.error`.

### Why
PR #33 corrigeait un site d'accès relation post-commit dans `publish_card`. L'utilisateur a signalé que l'erreur persistait en prod après merge. Sans observabilité, impossible de discriminer entre : (a) Railway pas encore redéployé, (b) un autre site `MissingGreenlet` non détecté, (c) un bug réseau réel. Cette PR rend les trois cas distinguables.

---

## [Released] — fix publish MissingGreenlet (PR #33, 2026-05-14)

### Fixed
- **`POST /api/v1/cards/{id}/publish` retournait `TypeError: Failed to fetch` au navigateur** — `CardService.publish_card` accédait à `card.user.username` ligne 138 après `await db.commit() + await db.refresh(card)`. Le `refresh` expirait toutes les relations, l'accès lazy déclenchait `MissingGreenlet` en pleine sérialisation HTTP, la requête mourait sans body. Côté UI : message « Impossible de contacter le serveur ». Fix : capture des scalaires (`username`, `card_slug`) avant `commit`, suppression du `refresh` superflu (les valeurs viennent d'être assignées en mémoire).

### Changed
- `agent/PITFALLS.md` §1.4 enrichi : ajout du symptôme côté frontend (`Failed to fetch` trompeur) et du cas vécu sur `publish_card`.

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
- **3 nouvelles pages** : `/features` (grille fonctionnalités dispo + en préparation), `/roadmap` (feuille de route MVP → Futur avec statuts), `/security` (crypto Ed25519, vérification, FAQ sécurité)
- **OpenGraph dynamique** : endpoint `GET /api/v1/og?title=&creator=` génère une image PNG 1200×630 via Pillow (DejaVu Serif, fond sombre, titre centré, accent bleu)
- **Meta `og:image` et `twitter:image`** sur les fiches publiques (`/@creator/card`) pointant vers l'endpoint OG
- **Page /about enrichie** : histoire du projet, valeurs (transparence, pérennité, liberté), liens vers /security et GitHub
- **Navbar mise à jour** : 5 entrées (Accueil, Fonctionnalités, Roadmap, Sécurité, À propos)
- **Dépendance backend** : `Pillow>=12.2.0` (génération OG images)
- **`.prettierignore`** : ignore `.svelte-kit/` et `build/` — Prettier ne vérifie plus les fichiers générés en CI

### Fixed
- **Logout** : `invalidateAll()` appelé après `auth.reset()` pour que le layout reload `data.user` — l'avatar Google ne reste plus affiché après déconnexion
- **Publish** : message "Impossible de contacter le serveur" au lieu de "Failed to fetch" en cas d'erreur réseau (TypeError catch)
- **get_current_user sans `: Request`** : ajout du type hint `request: Request` dans `sources.py:63` et `users.py:20` — FastAPI traitait `request` comme paramètre query → tous les endpoints sources retournaient 422 avec `{"detail": [{"type": "missing", "loc": ["query", "request"]}]}`
- **Texte "Pour qui?"** : ajout d'une 4e catégorie "Créateur·ice·s de contenu" + note "N'oubliez pas de citer les créateur·ice·s de contenu — ils et elles ne se considèrent pas toujours comme des vulgarisateurs scientifiques ou des journalistes." sur la page d'accueil et la page À propos
- **Typo** : "méthodologies" → "méthodologie" dans la carte journaliste

### Changed
- **Architecture du site** : passage de 2 à 5 pages de navigation, contenus distincts et non redondants
- **Navbar** : refonte des imports (api importé directement, Logout utilise `api.auth.logout()` au lieu de `fetch` brut)

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
