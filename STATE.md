# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-07-13**

---

## 🚨 P0 — Backend Railway DOWN (vérifié 2026-07-11)

Toutes les requêtes vers `filum-production-07bb.up.railway.app` renvoient `{"status":"error","code":404,"message":"Application not found"}`. Fiche démo 404, login mort, tous les parcours dynamiques HS. Le frontend Vercel est up. **Action manuelle requise** : vérifier le service Railway (crash-loop ? domaine détaché ? projet suspendu ?). Détails : [`UX-WALKTHROUGH-REPORT.md`](./UX-WALKTHROUGH-REPORT.md).

---

## Phase courante

**Phase 2 — Identité visuelle Philum v1 + corrections audit (juin 2026).**

- Logo refondu vers Pulsar-graph (CB12 + Z13 + stroke fond V18) déployé site-wide (PR #91 mergée).
- Customizer de logo `/sandbox/customize` livré : 4 sous-sandboxes, drag, palettes, saves localStorage, export SVG.
- Audit improvements appliqués : email leak fixé, CVE `python-jose` → `pyjwt`, déprécations `datetime.utcnow()` corrigées (PR #92 mergée).
- CI infra alignée : `pnpm/action-setup@v6`, `actions/setup-python@v6`, `actions/checkout@v6` (PR #93 mergée).

Avant cette phase, la **Phase 1 (MVP complet)** était terminée : jalons M1 (OAuth Google) + M2 (auth guard + extracteur URL) + M3 (rate limit, logs, backup) + Axe C (refonte attestation post-ADR-019) tous livrés. Flow end-to-end opérationnel : login → création → signature → attestation → publication.

---

## PRs ouvertes

| # | Branche | État CI | Sujet |
|---|---|---|---|
| #100 | `refactor/code-optimizations` | ✅ verte | Optimisations code (index morts, requête slug unique, dead code frontend, lucide-svelte retiré) |
| #101 | `fix/ux-walkthrough` | en cours | Fixes UX walkthrough (dark mode wizard, ConfirmDialog source, redirect publication, proxy 503) + rapport |
| en attente | `feat/waitlist` | — | Waitlist POST /waitlist + WaitlistForm home (plan acquisition PR 1/3) |
| en attente | `feat/card-claim` | — | Seed & claim v1 : is_seed, claim_requests, ClaimBanner (PR 2/3) |
| en attente | `feat/mcp-server` | — | Serveur MCP read-only sur /mcp (PR 3/3) |

> _Quand cette section est vide, plus rien n'est en attente côté review humaine._

---

## URLs production

- **Frontend** : https://filum-eight.vercel.app
- **Backend** : https://filum-production-07bb.up.railway.app — ❌ **DOWN, 404 "Application not found"** (vérifié 2026-07-11, cf. P0 ci-dessus)
- **API docs** : https://filum-production-07bb.up.railway.app/api/v1/docs
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau

---

## Stack effective

**Backend** : Python 3.12 · FastAPI async · SQLAlchemy 2.x async · Alembic · PostgreSQL (Railway) · Crypto Ed25519 + AES-GCM + HS256 (PyJWT) · Pillow (OG images) · slowapi (rate limit) · pytest (~70 tests).

**Frontend** : SvelteKit 2 · Svelte 5 (runes) · TypeScript · Tailwind · D3 v7 (graphe) · OGL (WebGL hero, lazy) · Vercel · pnpm 10 pinné · Logo Philum v1 (Pulsar-graph CB12 + Z13 palette).

**Analytics** : dbt-core sur DuckDB (job `dbt compile` en CI).

**Architecture OAuth** : Frontend → proxy SvelteKit `/api/[...path]` → Backend (cookies first-party). Backend lit `X-Filum-Public-Origin` (set par proxy) pour construire `redirect_uri` (cf. ADR-025).

---

## CI (workflows GitHub Actions)

3 workflows : `ci.yml`, `analytics.yml`, `security.yml`. Jobs (~16 total) : Lint/Test/Type-Check Backend + Frontend, Build Frontend, Analytics (dbt compile), Security Scan (Trivy), Static Analysis (Bandit), Vulnerability Check (Safety), Secrets Detection (TruffleHog), Dependency Review, CI Summary, Vercel preview.

Toutes les actions bumpées en juin 2026 (`pnpm v6`, `setup-python v6`, `checkout v6`).

---

## Variables d'environnement (Railway production)

```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://filum-production-07bb.up.railway.app
cors_origins           = ["https://filum-eight.vercel.app","http://localhost:5173"]
google_client_id       = <Google OAuth Client ID>
google_client_secret   = <Google OAuth Client secret>
debug                  = false
```

⚠️ **Toutes en lowercase** (ADR-010 — pydantic-settings `case_sensitive=True`).

Vercel : `BACKEND_URL=https://filum-production-07bb.up.railway.app` (env var serverless, jamais exposée navigateur).

---

## Bugs latents (non bloquants)

| Bug | Sévérité | Localisation |
|---|---|---|
| `impact_factor` toujours `null` | Faible | OpenAlex retiré, pas de fallback. Soit rebrancher une source, soit retirer le champ UI. |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5. |
| Wayback queue durability | Moyenne | `asyncio.create_task` perdu au restart Railway. Cf. F5 dans `13-audit-2026-05-26-followups.md`. |
| Pas de domaine custom | Feature | Brancher `philum.app` quand 1er ambassadeur prêt. |

---

## Prochaines étapes (par ordre d'impact/coût)

> Plan détaillé : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Court terme** (semaines)
- **F1** — `openapi-typescript` (gen auto des types TS depuis OpenAPI, prévient drift back/front) — effort 3-4h.
- **F4** — Endpoint `POST /cards/{id}/restore` (annule un soft-delete) — effort S.
- **F2** — Tests d'intégration sur `POST /cards/{id}/publish` (couvre le path qui a coûté 4 PRs en mai).

**Moyen terme** (déclencheurs naturels)
- **F5** — Queue Wayback durable (Postgres-backed + worker) quand > 50 sources/jour.
- **Phases 2-4 du rename Philum** — convertir en issues GitHub plutôt qu'attendre un gros chantier (cf. `.docs/14-philum-rename-migration.md`).
- **F3** — Tests Postgres au lieu de SQLite quand on ajoute un index partial / colonne JSONB.

**Long terme** (conditionnel à validation produit)
- **Axe A** — Stockage cloud R2 pour contenu original (décision dépend des interviews créateurs).
- **Axe B** — Archivage multi-cible (Wayback → Archive.today → Playwright + table `archive_attempts`).
- **F8** — Multi-tenancy si pivot B2B confirmé.
- Domaine custom `philum.app` + import Zotero/BibTeX/Obsidian + plugin navigateur (après 3-5 créateurs actifs).

---

## Décisions techniques majeures

Voir [`DECISIONS.md`](./DECISIONS.md) pour le détail. Les plus structurantes :

- **ADR-013** : pnpm 10 pinné
- **ADR-014** : `python-jose` → `PyJWT` (CVE)
- **ADR-019** : signature sur le triplet `(creator_id, content_url, attested_at)`, fiches mutables
- **ADR-020** : taxonomie sources 3 axes (`format` / `category` / `author_kind`)
- **ADR-024** : sandbox tunable → port prod
- **ADR-025** : proxy SvelteKit pour OAuth cross-origin
- **ADR-026** : topologie graphe (lune + Y-fork virtuel + perspective 3D)

---

## Commandes utiles

```bash
# Backend local
cd apps/backend
uv sync --all-extras
uv run uvicorn app.main:app --reload
uv run pytest tests/ -v
uv run alembic upgrade head
uv run ruff check app/ && uv run ruff format app/ && uv run mypy app/ --ignore-missing-imports

# Frontend local
cd apps/frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run check
pnpm run lint
pnpm run build

# CI
wsl gh run list --branch main --limit 5
wsl gh pr list
```

---

## Comment relancer une session

1. **Lire ce fichier** (snapshot court).
2. Pour le détail historique : [`CHANGELOG.md`](./CHANGELOG.md).
3. Pour les items en attente : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).
4. Pour les décisions techniques : [`DECISIONS.md`](./DECISIONS.md).
5. Pour l'agent IA autonome multi-sessions : [`agent/README.md`](./agent/README.md).
6. Vérifier l'état avec : `git log --oneline -10`, `wsl gh pr list`, `curl https://filum-production-07bb.up.railway.app/health`.
7. Choisir une tâche dans « Prochaines étapes » ci-dessus.
8. Branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite.

---

## Mettre à jour ce fichier

Quand la session apporte un changement significatif (PR mergée, phase qui change, URL prod modifiée, nouvelle ADR), **éditer la section pertinente** et bumper la date en haut. Pour les détails de la session (commits, root causes, bugs résolus), **écrire dans `CHANGELOG.md`** — pas ici.
