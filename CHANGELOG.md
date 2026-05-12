# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased]

### Added
- Itération 2 (ADR-017) : nouveau logo (arbre phylogénétique + graphe), badges « Source clé » + « Conflit d'intérêt déclaré », indicateurs typés (citations, impact factor, abonnés, vues), table `source_excerpts` avec extraits cités, plein écran sur le graphe, panneau de détail ancré au nœud cliqué (au lieu de coller au bord droit), SSR + JSON-LD + meta OG/Twitter/canonical sur la fiche publique pour le référencement classique et le GEO
- Migration 004 : colonnes `conflict_of_interest`, `citations_count`, `subscribers_count`, `views_count`, `impact_factor` sur `sources`, et nouvelle table `source_excerpts(source_id CASCADE, position, text, suggested_by_ai)`
- Section publique renommée « Sources citées » (ex « Liste éditoriale »), titres des sources calés à `text-base` pour rétablir la hiérarchie typographique
- Spec mode privé + intégrations Zotero/Obsidian/Notion (`.docs/09-private-mode-and-integrations.md`)

### Changed
- Cartographie : labels d'auteurs au-dessus des nœuds, seuils de zoom (< 0.7 rien, ≥ 0.7 auteur, ≥ 1.5 auteur + début du titre), nœud central étiqueté par créateur + pictogramme du type de contenu (plus de label « Fiche »)

### Removed
- Affichage des badges « Autorité élevée/moyenne/faible » côté UI (la colonne `authority_level` est conservée en base pour compatibilité ; remplacée à l'écran par les indicateurs structurés)
- Label « Fiche » sur le nœud central du graphe

### Security
- Aucune modification du `canonical_hash` payload : les nouveaux champs (indicateurs, excerpts, conflict_of_interest) sont volontairement hors signature, donc toutes les fiches déjà publiées restent vérifiables sans re-signature

- Graphe interactif des sources sur la fiche publique (ADR-016) : D3 v7 force-directed, sources colorées par type, sources avec parent en périphérie (plus petites, arêtes pointillées), drag/zoom/pan, animation cascade
- Panneau latéral détail au clic d'une source (slide-in droite desktop, bottom-sheet mobile, Escape, navigation vers le parent)
- `Source.parent_source_id` : FK self-référente nullable indexée matérialisant le citation graph (migration 003)
- Bibliographie démo enrichie : 14 sources réelles en neurosciences de la mémoire + 6 arêtes de citation, nouveau slug `/@example/memoire-et-cerveau`
- `lib/utils/source-colors.ts` : single source of truth des couleurs par type (hex D3 + classes Tailwind), partagé entre SourceGraph et SourceTypeBadge
- Déploiement Vercel du frontend : https://filum-eight.vercel.app, API base URL dynamique via `PUBLIC_API_BASE_URL`
- Déploiement Railway du backend en production (https://filum-production-07bb.up.railway.app), Postgres lié via `${{Postgres.DATABASE_URL}}`, migrations Alembic exécutées au boot (ADR-015)
- Coercition automatique `postgresql://` → `postgresql+asyncpg://` dans `config.py` (`field_validator` mode `before`) pour brancher la DB Railway sans transformation manuelle

### Fixed
- `/health/database` : wrap raw SQL en `text("SELECT 1")` pour SQLAlchemy 2.x (bug latent surface par le premier déploiement)
- `alembic/env.py` : import de `get_settings()` au lieu d'un `settings` inexistant (migrations crashaient à l'import)
- Dockerfile : port dynamique `${PORT:-8000}` (Railway injecte `$PORT`), et `alembic upgrade head` chaîné au CMD pour migrer au boot
- Trufflehog dans `ci.yml` : restreint à `pull_request` (failait sur push main avec `BASE and HEAD commits are the same`)
- `.env.example` aligné sur ADR-010 : toutes les clés en lowercase (UPPERCASE = silent fallback aux defaults sur Linux/CI)
- CLAUDE.md : structure réelle du backend (`apps/backend/app/`, pas `src/filum_api/`) et convention env vars lowercase
- STATE.md : flagging honnête de `extractors/` vide et `crypto/signing.py` stub
- Suppression du répertoire fantôme `apps/backend/app/api/{v1/endpoints}/` (résidu de brace-expansion ratée)

### Removed
- `.github/workflows/cd.yml` : workflow CD avec YAML mal formé (`workflow_dispatch` hors `on:`) et action fictive `railway-devrel/railway-actions@v1`. Remplacé par l'intégration GitHub native de Railway (ADR-015).
- `.github/workflows/dependency-review.yml` : doublon du job Dependency Review déjà dans `security.yml`, avec policy plus stricte qui bloquait sur des moderate CVEs non-exploitables
- `HANDOVER.md` : one-shot prompt de passation devenu obsolète après le merge MVP
- `apps/frontend/src/routes/dashboard/+page.server.ts` : load serveur redondant avec `+layout.ts`, redirect malformé
- `apps/frontend/src/tests/components/Button.test.ts` : incompat Svelte 5 + testing-library (à réécrire en follow-up)
- `apps/frontend/.pnpm-approve-builds.json` (artefact pnpm 11, ignoré par pnpm 10)
- `apps/frontend/pnpm-workspace.yaml` (réécrit par pnpm 11 avec un placeholder malformé ; inutile en mono-package)

### Security
- Migration `python-jose` → `PyJWT` 2.12.1 (ADR-014). Supprime `ecdsa@0.19.2` (CVE Minerva timing attack on P-256, HIGH) et ses transitives `pyasn1`, `rsa`. Non exploitable chez nous (HS256 pour JWT, Ed25519 via `cryptography`, pas d'ECDSA), mais bloquait la CI Dependency Review.

### Changed
- CI build-frontend (ADR-013) : pin pnpm 10.33.4 via `packageManager` dans `package.json`, retrait des workarounds pnpm 11 (`|| true` sur install, `pnpm exec vite build`, `verify-deps-before-run=false`, `continue-on-error` sur Type Check). `--frozen-lockfile` en CI, `pnpm-lock.yaml` commit.
- Tests AuthService renforcés : Ed25519 sign/verify roundtrip via `KeyManager.decrypt_private_key`, bounds tight sur l'expiry 24h, suppression de l'accès au privé `request._cookies`, remplacement des tests Pydantic triviaux par un round-trip JWT ↔ TokenPayload
- Tests d'intégration endpoints auth ajoutés sous `tests/integration/` : `/me` 401 sans token, `/me` 200 avec cookie, `/logout` clears cookie

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
