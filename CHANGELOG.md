# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased] — UI polish : dark mode, hero, hover effects, CTA fix (2026-05-15)

### Added
- **Hover lift effect** (`hover-lift` class in `app.css`) : cards on Features page, step cards, and audience cards now rise 3px on hover with border highlight.
- **Y-fork branch clusters** in hero SVG : two fork-shaped branch connections added for visual depth.
- **Star density increased** in hero SVG from ~13 to ~30 stars, with 6 twinkling animated stars.
- **`--bg-surface-secondary`** CSS custom property in `.dark` for theme-aware alternate surfaces.
- **`.cta-section` and `.hero-cta-light`** global CSS classes in `app.css` with proper dark-mode awareness (navy `#1A2A4A` / `#0D1525` backgrounds).

### Fixed
- **Hero text** restored to "Vous allez adorer partager vos références" (original pre-redesign tagline).
- **Dark mode tokens lightened** : `--bg-secondary` from `#0F0F11` → `#14141A`, `--text-primary` from `#EDEDED` → `#F5F5F5`, semantic colors saturated +15%.
- **Primary button** (`Button.svelte`) : replaced `bg-ink-primary text-white` (white-on-white in dark mode) with `bg-black text-white dark:bg-white dark:text-black`.
- **CTA section** : no longer inherits `rgb(var(--text-primary))` background (was near-black in light mode, light-gray in dark mode). Now uses dedicated dark navy (`#1A2A4A` / `#0D1525`).
- **`hero-cta-light`** button : white bg with `rgb(var(--text-primary))` text was invisible in dark mode (white bg, light gray text). Now uses `#1e1e2a` bg with `#f5f5f5` text.
- **Features page** : all 6 "Disponibles" cards had hardcoded `bg-white` — replaced with `bg-surface-primary`.
- **Security page** : `prose prose-slate` without `dark:prose-invert` made bold text illegible in dark mode.
- **About page** : same `prose prose-slate` issue fixed.
- **Hero SVG** : all node labels removed (Chercheur·euse, Institution, Média, École, Individu, Association) — only "Filum" center label kept.

### Changed
- **Step card hover** : added `translateY(-3px)` + border-color transition (was static).
- **Audience card hover** : increased lift from `-2px` to `-3px`.

---

## [Unreleased] — Source taxonomy redesign (3 orthogonal axes) — ADR-020 (2026-05-14)

### Added
- **3 axes obligatoires sur `Source`** : `format` (5 valeurs : texte/video/image/audio/data), `category` (12 valeurs : article-scientifique, preprint, article-presse, communique, documentaire, interview, podcast, blog, post-social, livre, page-web, notes), `author_kind` (9 valeurs : chercheur, media, institution-publique, gouvernement, ecole, laboratoire, entreprise, asso, individu).
- **Dropdown « Cette source en cite une autre déjà ajoutée ? »** dans le formulaire d'ajout de source. Persiste `parent_source_id`, rendu en pointillés dans le graphe.
- **3 nouveaux composants badge** : `AuthorKindBadge` (coloré par auteur), `FormatBadge`, `CategoryBadge` (variantes neutres).
- **ADR-020** dans `DECISIONS.md` documentant la décision et le mapping de migration.
- Tests : 4 nouveaux vitest sur `author-colors`. Tests pytest schemas mis à jour (17 cas pour la nouvelle taxonomie).

### Changed
- **Graphe coloré par `author_kind`** au lieu de `source_type` (signal épistémique le plus informatif pour le lecteur).
- **`CardStats`** re-keyé : `peer_reviewed` / `institutional` / `press` / `video` / `image` / `original` → `chercheur` / `media` / `institution_publique` / `individu`. Frontend public card adapte les 2 tuiles statistiques.
- **Endpoints sources** : ajout/édition/suppression désormais autorisée sur fiches publiées (cohérent avec ADR-019 sur la mutabilité des fiches).
- **Hero accueil** : SVG redessiné — lignes droites (plus de courbes), 2 arêtes en pointillés entre sources pour illustrer la feature parent_source_id, labels mis à jour avec la nouvelle taxonomie (Chercheur·euse / Média / Institution / École / Individu / Association).
- **Seed démo** : 16 sources réécrites avec la taxonomie 3 axes ; les 7 liens parent_source_id conservés.

### Fixed
- **`POST /cards/{id}/sources` ignorait silencieusement `parent_source_id`** : le champ était accepté par Pydantic mais jamais passé au constructeur `Source(...)` dans `sources.py:138`. Le seed le contournait par insertion directe ; depuis l'UI il était impossible de créer un lien parent. PITFALLS mis à jour avec ce cas d'école.
- **Hero copy** : « chaque contenu original que vous revendiquez » → « chaque création que vous revendiquez » (2 occurrences). Collision sémantique levée avec l'ancien `source_type=original`.

### Removed
- Colonnes `sources.source_type` et `sources.authority_level` (migration 007). `AuthorityLevel` (legacy) supprimé du modèle, schéma, frontend.

---

## [Released] — UX & accessibility pass (PR #43, 2026-05-14)

### Added
- **Menu hamburger mobile** dans la header : sur viewport `<md`, les onglets Fonctionnalités/Roadmap/Sécurité/À propos étaient invisibles. Désormais accessibles via un drawer sous la header avec gestion `aria-expanded`/`aria-controls` et fermeture sur Escape.
- **Boutons Voir / Éditer / Supprimer sur les fiches publiées** du dashboard. Auparavant seul un lien "voir" couvrait toute la card — impossible d'éditer une fiche publiée pourtant mutable depuis ADR-019. Édition réutilise la route `/dashboard/new/{id}/sources`.
- **Compteurs récap** dans le header du dashboard (X brouillons, Y publiées) avec skeleton pendant le chargement.
- **`+error.svelte`** : page 404/erreur custom avec CTA retour accueil + fiche démo, ou lien GitHub Issues pour les 5xx.
- **`/privacy`** : page stub minimale (le lien footer renvoyait sur du 404).
- **Illustration SVG dédiée** dans le hero d'accueil : graphe stylisé multi-types de sources (couleurs depuis `source-colors.ts`), nœud central animé, halo radial. Layout passe en 2 colonnes responsive avec background gradient subtil.

### Changed
- **Labels dynamiques sur les boutons submit** (création fiche, ajout source, publication) : "Création…"/"Ajout…"/"Publication…" pendant la requête + `disabled` pendant le loading pour empêcher le double-clic.
- **Menu utilisateur (avatar dropdown)** : ferme sur Escape via handler global, en plus du clic extérieur.

### Fixed
- `.gitignore` : ajout de `.claude/` (état local de l'agent).

---

## [Released] — publish ACTUAL fix : tz-aware datetime on TIMESTAMP WITHOUT TIME ZONE (PR #36, 2026-05-14)

### Fixed
- **Root cause publish bug** (résisté à PR #33 et #34) : `CardService.publish_card` faisait `card.signed_at = datetime.now(UTC)` sans `.replace(tzinfo=None)`. La colonne `DateTime` SQLAlchemy (sans `timezone=True`) est mappée à `TIMESTAMP WITHOUT TIME ZONE` côté PostgreSQL → asyncpg refuse les datetimes tz-aware avec `DataError: can't subtract offset-naive and offset-aware datetimes`. Le commit était aborté, la session passait en état "transaction aborted", `get_db`'s post-yield `await session.commit()` retentait et échouait à nouveau → la réponse était interrompue mid-stream → le navigateur voyait `ERR_FAILED` + "blocked by CORS policy" alors que CORS marchait sur tous les autres endpoints. Symptôme trompeur ++.
- **Diagnostic** : exposé via `/health/publish-diagnose` (ajouté PR #35) qui renvoie le traceback complet. Sans ce endpoint, on aurait continué à chasser des fantômes.

### Added
- **Rollback défensif dans le `try/except` de publish endpoint** : si une exception est levée pendant `publish_card`, on rollback la session avant de retourner le JSONResponse 500. Ça évite que `get_db` cleanup ne retente un commit sur session aborted et ne corrompe le stream de la réponse (cause profonde de l'absence de CORS dans la réponse d'erreur).

### Changed
- `agent/PITFALLS.md` §1.5 enrichi : ajout du symptôme tz-aware sur asyncpg (qui se confond avec un bug MissingGreenlet ou CORS), du cas vécu, et du chemin de diagnostic via `/health/publish-diagnose`.

---

## [Released] — publish diagnostics + safety net (PR #34, 2026-05-14)

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
