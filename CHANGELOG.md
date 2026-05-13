# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased]

### Added
- **Embranchement en Y** dans le graphe interactif : quand deux sources du même auteur citent le même parent, un nœud de jonction est créé automatiquement (arêtes Kandel → Nader → 2 papiers Nader)
- **Source YouTube** Artem Kirsanov sur la neuroscience de la mémoire (seed demo)
- **Deuxième source Karim Nader** : review Nature 2007 sur la reconsolidation, même auteur et même parent que l'article 2000 → démonstration de l'embranchement Y
- **Types de source** `video` (Documentaire→Vidéo) et `image` (Illustration→Image)

### Changed
- **Logo** : 6 branches dédoublées en 12 (embranchement en Y), suppression des lignes pointillées d'arrière-plan
- **Graphe interactif** : étiquette « Vidéo » supprimée du nœud central, créateur centré au-dessus du nœud (zoom ≥ 0.7), titre au-dessus du créateur (zoom ≥ 1.5)
- **Labels types source** : Peer-reviewed→Article scientifique, Original→Contenu original, Documentaire→Vidéo, Illustration→Image
- **Conflits d'intérêt** : rouge→ambré, icône ⚠ supprimée, badge conservé sans alarme
- **En-tête fiche publique** : layout compact (avatar + créateur + titre sur une ligne, description en sous-titre), hauteur du graphe augmentée (68vh→75vh)
- **Page d'accueil** : nouveau tagline « Vous allez adorer partager vos références », correction « bibliography »→« bibliographie »
- **Démo** : 18 sources (au lieu de 16), 8 arêtes de citation, ajout vidéo YouTube + review Nader
- **CI/CD** : `@sveltejs/vite-plugin-svelte` ^5→^6, `vitest` ^2→^3 (résout le crash Test Frontend, compatible vite@6)

### Removed
- Badge vérifié (coche bleue) sur l'avatar de la fiche publique
- Panneaux conflit d'intérêt expansés (gros bloc rouge) — le badge textuel ambré reste

### Fixed
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
