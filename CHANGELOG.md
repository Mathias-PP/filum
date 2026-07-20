# Changelog

> Historique des versions du projet Filum. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).
>
> **Types de changements** : `Added` (nouvelles fonctionnalités), `Changed` (modifications), `Deprecated` (fonctionnalités obsolètes), `Removed` (suppressions), `Fixed` (corrections), `Security` (correctifs de sécurité).

---

## [Unreleased] — Import URL → fiche brouillon + rate-limit MCP + hero fix + Dependabot (2026-07-20)

### Added
- **`POST /api/v1/import/from-content-url`** (PR #152/#154) : un cran au-dessus de `/import/paste`. L'utilisateur donne l'URL d'un contenu (article, billet), Philum extrait titre/description via `url_extractor`, fetch le HTML, isole la section « References » via une short-list de sélecteurs CSS (Frontiers, PMC, Nature, `#references`, `.ref-list`…), passe le texte au LLM + regex avec dédup DOI-aware, retourne un draft `{card, sources, skipped, references_section_found, fetch_status}`. Auth requise, rate-limit 5/hour, SSRF-safe, cap HTML 3 MB, cap texte LLM 60 kB. Nettoyage systématique des `script/style/svg` avant analyse (bruit + coût LLM ×3). Statut fetch explicite : `ok` / `unreachable` / `not_html`.
- **UI `/dashboard/from-url`** (PR #154) : 2 étapes URL → preview. Bouton « Depuis une URL » sur `/dashboard` + cross-link sur `/dashboard/new`. Preview éditable (titre/slug/desc/plateforme, slug auto-dérivé du titre, guess platform depuis hostname), sources cochables individuellement, boutons « Tout cocher/décocher », compteur de progression `5/12` pendant la création séquentielle des sources, `beforeunload` warning si l'utilisateur ferme la page pendant la création, bandeau différencié selon `fetch_status` (rouge unreachable / bleu not_html / vert refs found / warn fallback).
- **Rate-limit `/mcp/` 60/min par IP** (PR #147) : le mount ASGI `/mcp` bypassait slowapi. Middleware HTTP dédié dans `main.py` réutilise la lib `limits` (déjà embarquée par slowapi). 429 + `Retry-After: 60`. Ferme le seul point ouvert de la revue MCP.

### Changed
- **PRs Dependabot mergées le 2026-07-20** : `vitest 4.1.10`, `svelte-check 4.7.3`, `svelte 5.56.6`, `@sveltejs/kit 2.70.1`, `eslint-plugin-svelte 3.22.0`, `svelte-eslint-parser 1.8.0`, `prettier 3.9.5` (reformat de `legacy-adapter.ts`), `@types/node 26.1.1`, `autoprefixer 10.5.4`. PR **#156 tailwind v4 fermée** (breaking change, migration dédiée nécessaire).
- **Dédup `_dedupe_key` DOI-aware** (PR #151) : nouvelle fonction qui extrait le DOI de l'URL (Frontiers, Wiley, Springer, PLOS, doi.org) et retourne `doi:{doi.lower()}` comme clé canonique. Résout le bug vécu où `frontiersin.org/…/10.3389/fpsyg.2018.01561/full` et `doi.org/10.3389/fpsyg.2018.01561` produisaient deux entrées identiques dans multi-liens/paste.

### Fixed
- **`ruff B904`** dans l'endpoint `from-content-url` (PR #154, dette de #152 qui avait cassé la CI de `main`). Toutes les PRs héritières redevenues vertes après merge.
- **Hero pulsar — ligne moon passe devant le nœud parent** quand la moon passe devant (PR #148/#149/#150, 3 itérations). v1 échouait car copie du test 3D pulsar sans adapter au ratio z/radius bien plus petit (moon.z max 0.098 vs radius parent 0.09). v2 (critère global `n.z > ancZ`) donnait un fade non progressif. **v3 = deux corrections combinées** : amplitude z de l'orbite locale de la moon passée de `0.35` à `0.9` (ratio z/radius 3× comme les nœuds/pulsar) + test pixel-par-pixel `smoothstep(0, ancR*0.35, lineZ - anchorFrontZ)` pour l'émergence progressive depuis le bord.

### Notes
- Backend : **197/197 tests verts** (191 → 197 avec 6 nouveaux tests import unitaires + 2 tests rate-limit MCP + 3 tests endpoint `from-content-url`).
- ⚠️ **VM prod pas encore redéployée** : `POST /api/v1/import/from-content-url` et le rate-limit `/mcp/` seront effectifs après `git pull` + `docker compose up -d --build` sur la VM.

---

## [Unreleased] — Migration hébergement GCP + Supabase (2026-07-19)

### Changed
- **Hébergement backend** : Railway (DOWN depuis ~2026-07-11) → VM GCP e2-micro always-free us-central1, Docker Compose (`infra/oracle/docker-compose.micro.yml` : backend + Caddy auto-TLS), domaine `philum-api.duckdns.org` avec IP statique. Cf. ADR-028.
- **Base de données** : Postgres Railway → Supabase free tier (Session pooler 5432). Base neuve : 10 migrations Alembic + seed démo, secrets régénérés (l'ancienne `master_encryption_key` Railway était un placeholder littéral).
- **Vercel** : `BACKEND_URL` basculée vers `https://philum-api.duckdns.org` ; redirect URI DuckDNS ajoutée au client OAuth Google.
- Vérifié end-to-end : `/health` HTTPS, fiche démo, login Google → dashboard.

### Notes
- Oracle Cloud abandonné pour l'instant : 525 tentatives de VM sur 4 jours, 100% « Out of capacity » (boucle retry laissée active).
- Railway décommissionnable (gardé en secours quelques jours).

---

## [Unreleased] — Philum v1 logo déployé site-wide (2026-06-02)

### Changed
- **`Logo.svelte`** : refonte complète vers le design Philum v1 validé en `/sandbox/customize`. Composition Pulsar-graph (pulsar central + 2 normaux NE/WSW + Y-fork NW + parent-lune SE) avec palette Z13 auteur-kind, stroke fond blanc V18 et dark rim fin. Pulsar 3D via radial gradient pour le variant `color`.
- **Composant Logo** accepte désormais 3 props :
  - `variant: 'color' | 'dark' | 'bw'` — `color` (couleur sur fond clair, défaut), `dark` (blanc sur fond sombre), `bw` (impression noir & blanc).
  - `withWordmark: boolean` — ajoute « Philum » serif Georgia à droite du graph.
  - `size` et `className` conservés.
- **`+layout.svelte`** : nav header utilise désormais `<Logo variant="color">` sur fond clair et `<Logo variant="dark">` sur fond sombre (swap via `block dark:hidden` / `hidden dark:block`).
- **`static/favicon.svg`** : redessiné en cohérence avec le variant `color` du nouveau Logo (version statique sans gradient pour rendu propre à 16/32 px).

### Removed
- Ancien design Logo V11 (6 branches monochromes à 60°) — remplacé par Philum v1.

---

## [Unreleased] — Philum v1 logo site-wide + audit improvements + CI bumps (2026-06-02)

### Added (PR #91 — feat/philum-v1-logo, mergée)
- **`Logo.svelte`** refondu vers le design Philum v1 validé en `/sandbox/customize` : Pulsar-graph (CB12 disposition + Z13 palette + stroke fond V18 + dark rim fin + pulsar 3D radial gradient).
- **3 variants** via prop `variant: 'color' | 'dark' | 'bw'` + option `withWordmark`.
- **Layout navbar** swap automatique `color` ↔ `dark` selon le thème.
- **`favicon.svg`** redessiné cohérent avec le nouveau logo.

### Fixed (PR #92 — feat/audit-improvements, mergée)
- **Privacy leak** : email personnel développeur (`mathias.pinault@hotmail.fr`) remplacé par `contact@philum.app` dans le User-Agent envoyé par `url_extractor.py` à chaque site scrapé.
- **CVE `python-jose`** : remplacé par `pyjwt` dans `requirements.txt` (déjà utilisé partout, aligné sur `pyproject.toml`).
- **Déprécations `datetime.utcnow()`** : 3 modèles (`source.py`, `biblio_card.py`, `audit_event.py`) factorisent désormais un helper `_utcnow_naive()` cohérent avec `source_excerpt.py`.
- **`Dockerfile.migrate`** : aligné sur le Dockerfile principal (`pyproject.toml` + `uv sync --frozen`).

### Changed (PR #93 — chore/deps/github-actions-bump, mergée)
- **GitHub Actions** : `pnpm/action-setup` v4 → v6, `actions/setup-python` v5 → v6, `actions/checkout` v4 → v6 (consolidation des PRs dependabot #88, #89, #90).

### Docs
- **`STATE.md`** réécrit en version courte (1 page, structure fixe). Historique détaillé déplacé dans `CHANGELOG.md`.
- **`.docs/14-philum-rename-migration.md`** : Phase 1 marquée MERGÉE, Phases 2-4 reformulées comme triggers naturels.
- **`.docs/13-…-followups.md` ↔ `.docs/15-audit-improvements-plan.md`** : cross-références ajoutées (les 2 docs servent des usages distincts : 13 = items long terme priorisés, 15 = session-specific juin 2026 + windmills documentés).

---

## [Unreleased] — Logo refonte itérative + sandbox customizer (2026-06-02)

### Added
- **`/sandbox/logo`** : trois nouveaux batchs explorant la signature visuelle.
  - **Batch A v4** (40 dispositions de nœuds) avec Y01 special nodes + 2 normaux variés (préférence user : éviter l'alignement horizontal symétrique).
  - **Batch W v4** (40 variants couleurs) avec disposition CB12 (NE + WSW) + **stroke fond blanc style V18** sur chaque sphère (cassure visuelle de la ligne au bord du cercle) + dark rim fin. Cumule Z13 auteur-kind, halos colorés, sphère 3D, quasar, X-spikes, anneaux orbitaux.
  - **Batch W v5** (30 variants exploratoires) sans contrainte de fond/rim : mono couleur, palette hero Z12, gradients, duotones.
- **`/sandbox/customize`** : page de customisation pleinement interactive du logo.
  - 4 sous-sandboxes (Référence clair / Dark theme / Logo + wordmark / Noir & blanc) avec configs indépendantes.
  - Drag souris sur tous les nœuds (pulsar, normaux, jonction Y-fork, twins, parent, lune) — conversion coords via `getScreenCTM().inverse()`.
  - Style **par nœud individuel** : chaque normal/twin/parent/lune porte son propre fill, rim, rimWidth, size.
  - Add/remove dynamique des normaux, bouton « appliquer ce style à tous ».
  - Zoom canvas 30%–300% via slider.
  - 8 palettes prédéfinies (Z13, Z13 + 3D, Z12 pastel, mono slate/blue/emerald, dark, N&B) qui itèrent sur tous les nœuds.
  - Wordmark configurable (texte, position X/Y, taille, couleur, police serif/sans, graisse, letter-spacing).
  - Export SVG par sandbox, copier-coller config entre sandboxes.

### Changed
- **Étymologie du nom Philum** (`/about`) : reformulée en référence au *phylum* biologique (branche de l'arbre du vivant) plutôt qu'au latin *filum*.

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
