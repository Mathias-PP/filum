# PROJECT_SNAPSHOT — Filum en 3 minutes

> Vue condensée pour qu'un agent qui découvre le projet ait l'essentiel en un seul fichier. **N'est pas la source de vérité** — c'est un index commenté. Pour chaque sujet, suivre le lien vers le fichier autoritaire.

---

## C'est quoi Filum

Infrastructure ouverte de **provenance et de filiation** pour les contenus numériques. Un créateur (vulgarisateur scientifique d'abord, puis journaliste, chercheur) transforme la bibliographie de ses vidéos / articles / podcasts en une **fiche publique navigable** : sources horodatées, signées cryptographiquement (Ed25519), reliées en graphe interactif.

**Vision longue (5-10 ans)** : devenir la couche standard de citation du web, ce que HTTPS est à la confidentialité. Fondation à but non lucratif détenant le protocole + société commerciale finançant via services premium.

→ [`.docs/00-vision.md`](../../.docs/00-vision.md)

---

## C'est qui derrière

**Mathias Pinault** (`mathias.pinault@hotmail.fr`, GitHub `Mathias-PP`).
- Solo dev avec assistance IA.
- Pas de budget MVP. Tout doit tourner sur les free-tiers.
- Travaille en français mais le code et les commits sont en anglais.

---

## État au 2026-05-14

**Phase 1 — MVP complet + Axe C (ADR-019) livré**

- Backend live sur Railway : https://filum-production-07bb.up.railway.app
- Frontend live sur Vercel : https://filum-eight.vercel.app
- Fiche démo publique avec graphe D3 18 sources : https://filum-eight.vercel.app/@example/memoire-et-cerveau
- **Axe C déployé** : migration 006, table `content_attestations`, endpoints attestation, seed signé. La signature porte sur le triplet `(creator_id, content_url, attested_at)` — les fiches sont désormais mutables.
- **2 crashs prod résolus** : (1) DROP INDEX inexistant dans migration 006, (2) `created_at=NULL` dans le modèle `ContentAttestation`
- CI 9/9 verte sur main

**Ce qui manque pour un produit publiable** :
- Import Zotero/BibTeX/Obsidian pour réduire la friction
- Plugin navigateur pour ajout de source en un clic
- Export PDF/CSV/Excel/JSON
- Collaboratif (édition à plusieurs)
- API publique + serveur MCP

→ [`STATE.md`](../../STATE.md) pour l'état complet et vérifié

---

## Stack (non négociable sauf ADR explicite)

| Couche | Tech |
|---|---|
| Backend | Python 3.12, FastAPI async, SQLAlchemy 2.x async, Alembic |
| BDD transactionnel | PostgreSQL (Railway plugin) |
| Analytics | DuckDB + dbt-core (présent mais inerte en runtime) |
| Frontend | SvelteKit 2, Svelte 5, TypeScript, Tailwind |
| Crypto | `cryptography` (Ed25519, AES-GCM, SHA-256), `PyJWT` (HS256) |
| Archivage | API Wayback Machine |
| Identité | Google OAuth (à brancher) |
| Package mgr | `uv` (Python), `pnpm 10.33.4` pinned (Node) |
| Lint/format | `ruff` (Python), `eslint 9` + `prettier` (Node) |
| Tests | `pytest` (backend), `vitest` (frontend) |
| Déploiement | Railway (backend) + Vercel (frontend) |

→ [`.docs/02-tech-architecture.md`](../../.docs/02-tech-architecture.md), [`CLAUDE.md`](../../CLAUDE.md)

---

## Structure du repo

```
filum/
├── README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md, SECURITY.md
├── STATE.md, DECISIONS.md, CHANGELOG.md   # documents vivants
├── Makefile                                # targets dev/test/lint/migrate/seed
├── .docs/00-…11-…md                        # specs (figées 00-09, vivantes 10+)
├── agent/                                  # instructions agent autonome (ce dossier)
├── apps/
│   ├── backend/                            # FastAPI
│   │   └── app/{models,schemas,api/v1,services,crypto,extractors,scripts}
│   ├── frontend/                           # SvelteKit
│   │   └── src/{routes,lib/{components,stores,api,utils}}
│   └── analytics/                          # dbt project (inerte en runtime)
├── infra/                                  # Docker
├── notebooks/                              # exploration
├── scripts/                                # setup, dump, etc.
├── .github/{workflows,ISSUE_TEMPLATE}/
└── .opencode/                              # config agent opencode
```

---

## Modèle de données (essentiel)

- **`users`** : `id`, `slug` (unique), `email`, `display_name`, `avatar_url`, `encrypted_private_key`, `public_key`
- **`biblio_cards`** : `id`, `creator_id` (FK users), `slug` (unique par créateur), `title`, `description`, `content_url`, `platform`, `published_at` (plus de `canonical_hash`/`signature`/`signed_at` — migré vers `content_attestations`)
- **`content_attestations`** : `id`, `user_id` (FK users), `content_url`, `attested_at`, `canonical_hash`, `signature`, `created_at` — signature du triplet `(creator_id, content_url, attested_at)` via Ed25519
- **`sources`** : `id`, `biblio_card_id` (FK), `url`, `title`, `authors`, `format` / `category` / `author_kind` (taxonomie 3 axes — ADR-020, remplace ex-`source_type` + `authority_level`), `published_date`, `annotation`, `is_pivot`, `archive_url`, `archive_status`, `parent_source_id` (FK self, rendu dashed dans le graphe), `citations_count`, `impact_factor`, `subscribers_count`, `views_count`, `conflict_of_interest`
- **`source_excerpts`** : `id`, `source_id` (FK CASCADE), `position`, `text`, `suggested_by_ai`
- **`audit_events`** : audit log des actions sensibles

⚠️ **Pivot crypto (ADR-019, 2026-05-14)** : la signature porte sur le **lien créateur·ice ↔ contenu** (triplet `(creator_id, content_url, attested_at)`), plus sur la fiche bibliographique. Les fiches sont mutables. Migration `006_remove_card_signature` + nouvelle table `content_attestations` à venir. Cf. [`PITFALLS.md`](../PITFALLS.md) 1.3 et `DECISIONS.md` ADR-019.

→ [`.docs/03-data-model.md`](../../.docs/03-data-model.md)

---

## API en bref

Toutes les routes sous `/api/v1/`. Auth via cookie session HS256.

- `GET /health`, `GET /health/database` — sondes
- `GET /auth/google/login`, `GET /auth/google/callback` — OAuth (à compléter)
- `GET /auth/me`, `POST /auth/logout`
- `POST /cards`, `GET /me/cards`, `PATCH /cards/{id}`, `POST /cards/{id}/publish`, `DELETE /cards/{id}`
- `POST /cards/{id}/sources`, `GET /sources?card_id=...`, `PATCH /sources/{id}`, `DELETE /sources/{id}`
- `GET /sources/extract?url=…` — extracteur Crossref + HTML
- `GET /og?title=...&creator=...` — image OpenGraph dynamique (Pillow)
- `GET /{creator_slug}/{card_slug}` — lecture publique
- `GET /users/{slug}` — page-identité

→ Swagger live : https://filum-production-07bb.up.railway.app/api/v1/docs

---

## Conventions de nommage

- Fichiers Python : `snake_case.py`
- Fichiers Svelte : `kebab-case.svelte` (composants), `+page.svelte` (routes)
- Modèles SQLAlchemy : `PascalCase`, tables Postgres : `snake_case` pluriel
- Routes API : `kebab-case`, pluriel
- Variables d'env : **`lowercase`** (ADR-010 — `case_sensitive=True` pydantic)
- Branches Git : `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`, `test/`

---

## Variables d'env clés (Railway prod)

```
database_url           # postgresql+asyncpg://... (coercé depuis postgresql://)
session_secret         # 32 bytes hex
master_encryption_key  # 32 bytes hex pour AES-GCM
frontend_base_url      # https://filum-eight.vercel.app
backend_base_url       # https://filum-production-07bb.up.railway.app
cors_origins           # JSON array
debug                  # false en prod
# Non configurées : google_client_id, google_client_secret, google_redirect_uri,
# wayback_api_key, duckdb_path
```

⚠️ Toutes en **lowercase**. UPPERCASE = silent fallback aux defaults sur Linux/CI.

---

## CI (9 jobs verts requis sur main)

1. Security Scan (Trivy + TruffleHog)
2. Lint Backend (ruff)
3. Type Check Backend (mypy)
4. Test Backend (pytest, 72 tests)
5. Lint Frontend (eslint + prettier)
6. Test Frontend (vitest)
7. Build Frontend (vite, frozen lockfile)
8. Analytics Check (dbt compile)
9. Container Build (Docker build check)

Pas de workflow CD séparé — Railway déploie auto à chaque push main (ADR-015).

---

## Workflow git

- Solo dev. Toujours via PR vers `main`. Squash-merge. Branche supprimée après merge.
- `git` via WSL uniquement sur Windows (`wsl bash -lc 'cd /mnt/c/Users/mathi/Documents/filum_project/filum && git …'`).
- `gh` CLI dispo via WSL, déjà authentifié.
- Vérifier l'état distant **avant** `gh pr merge` (cas vécu : commit manquant dans squash).

→ [`agent/GIT_WORKFLOW.md`](../GIT_WORKFLOW.md)

---

## Pièges les plus coûteux (top 6)

1. Revision Alembic > 32 char → crash-loop Railway → [`PITFALLS.md`](../PITFALLS.md) §1.1
2. Double `create_index` après `index=True` dans `Column` → [`PITFALLS.md`](../PITFALLS.md) §1.2
3. Variable d'env UPPERCASE silently ignorée → [`PITFALLS.md`](../PITFALLS.md) §1.6
4. pnpm 11 casse tout — rester sur 10.33.4 → [`PITFALLS.md`](../PITFALLS.md) §2.1
5. Modifier la forme du payload `content_attestation` signé → attestations existantes invérifiables → [`PITFALLS.md`](../PITFALLS.md) §1.3
6. `default=None` dans un modèle SQLAlchemy override `server_default` de la DB → `NotNullViolationError` → [`PITFALLS.md`](../PITFALLS.md) §1.8

→ [`PITFALLS.md`](../PITFALLS.md) liste complète

---

## Ce qu'il faut faire MAINTENANT (jalon courant)

Cf. [`STATE.md`](../../STATE.md) et [`.docs/12-next-steps.md`](../../.docs/12-next-steps.md).

Au 2026-05-14, **Axe C (ADR-019) livré** — MVP stabilisé + refonte backend attestations déployée. 2 crashs prod résolus en chemin.

Plan 3 axes mis à jour (détail dans `.docs/12-next-steps.md`) :
- **P0** ✅ Axe C : refonte backend post-ADR-019 — **LIVRÉ**
- **P1** Axe B : archivage multi-cible (Wayback + Archive.today + Playwright snapshot)
- **P2** Validation produit (3 interviews créateurs cibles avant Axe A)
- **P3** Axe A : stockage cloud R2 + Internet Archive (conditionnel à P2)

Prochaine étape : P1 (Axe B — archivage multi-cible).

---

*Ce snapshot doit rester court (< 250 lignes). Si tu as besoin de plus de détail, suivre les liens.*
