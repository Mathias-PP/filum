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

### Fixed
- CI build-frontend : `|| true` sur `pnpm install` pour compatibilité pnpm 11 (ERR_PNPM_IGNORED_BUILDS)
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
