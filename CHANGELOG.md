# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased]

### Added
- Specs initiales du projet (`.docs/`)
- Manifeste fondateur
- Maquettes de fiche bibliographique
- Choix de stack arrêtés
- Tests unitaires AuthService : création JWT, authentification cookie/bearer, token expiré, soft-delete, création utilisateur Google OAuth (15 tests)
- Conftest avec fixtures async DB (SQLite + aiosqlite), auth service, test user, session token
- Test sign/verify Ed25519 roundtrip dans `test_create_user_from_google_generates_usable_keypair` (déchiffre la clé privée via KeyManager, signe, vérifie avec la publique)
- Tests d'intégration endpoints auth (`tests/integration/test_auth_endpoints.py`) : /me 401 sans token, /me 200 avec cookie, /logout clears cookie

### Fixed
- CI build-frontend (ADR-013) : pin pnpm 10.33.4 via `packageManager` dans `package.json` ; suppression de tous les workarounds pnpm 11 (`|| true` sur install, `pnpm exec vite build`, `verify-deps-before-run=false`, `continue-on-error` sur Type Check) ; suppression de `kit.vitePlugin.inspector` (SvelteKit 2)
- Frontend : passage à `--frozen-lockfile` en CI (builds déterministes, `pnpm-lock.yaml` commit)

### Security
- Migration `python-jose` → `PyJWT` 2.12.1 (ADR-014). Supprime `ecdsa@0.19.2` (CVE Minerva timing attack on P-256, HIGH) et ses transitives `pyasn1`, `rsa`. Non exploitable chez nous (HS256+Ed25519, pas d'ECDSA), mais bloquait la CI Dependency Review.

### Removed
- `apps/frontend/.pnpm-approve-builds.json` (artefact pnpm 11, ignoré par pnpm 10)
- `apps/frontend/pnpm-workspace.yaml` (réécrit par pnpm 11 avec un placeholder malformé ; inutile en mono-package)
- CI env vars : passage en lowercase pour compatibilité `case_sensitive=True`
- CI cherry-pickée sur `feat/infrastructure-and-backend-mvp`
- Remote Git mis à jour : `filum_project` → `filum`

### Changed
- `case_sensitive=True` dans pydantic-settings → toutes les variables d'environnement en lowercase

---

## [0.0.1] — Pré-MVP, planification

**Date** : 2026-04

État initial du projet. Aucun code, uniquement les specs et la vision.

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
