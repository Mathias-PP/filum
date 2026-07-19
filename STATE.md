# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-07-19**

---

## ✅ État production vérifié (2026-07-19)

**Prod migrée Railway → GCP + Supabase** (cf. ADR-028). Vérifié par curl + parcours navigateur :
- `https://philum-api.duckdns.org/health` → `{"status":"ok","version":"0.1.0"}` (HTTPS Let's Encrypt via Caddy)
- Fiche démo `https://filum-eight.vercel.app/@example/memoire-et-cerveau` → 200, sources + graphe OK
- Login Google → dashboard OK (redirect URI DuckDNS ajoutée au client OAuth ; l'URI Railway existe encore, à retirer)

Infra : VM GCP e2-micro us-central1 always-free (Ubuntu 24.04, swap 2 GB, Docker Compose `infra/oracle/docker-compose.micro.yml` : backend + Caddy) · Postgres Supabase free (Session pooler **5432**, jamais 6543) · DuckDNS + IP statique GCP. 10 migrations Alembic + seed démo appliqués sur base neuve (secrets régénérés — l'ancienne `master_encryption_key` Railway était un placeholder).

**Railway est décommissionnable** (laissé en secours quelques jours). Boucle retry Oracle (WSL) toujours active en arrière-plan si A1 Paris se libère.

---

## Phase courante

**Phase 3 — Features d'adoption (juillet 2026) : imports/exports, IA, extension, API.**

Livré (mergé ou en PR, cf. tableau) : exports multi-formats (JSON/CSV/BibTeX/Markdown/xlsx/**docx**), imports (BibTeX/CSL-JSON/Markdown/PDF + biblio collée via LLM + multi-liens), citations IA vérifiées verbatim, extraction métadonnées durcie (DOI éditeurs + **PII ScienceDirect via Crossref**), fix session 7 jours (P0 « fiches disparues » = illusion causée par expiration 24h + 401 silencieux du dashboard — **aucune donnée perdue**, vérifié en prod), durcissement sécurité MCP, extension navigateur MV3 (`apps/extension/`), page `/developers` (docs API + MCP).

⚠️ **La VM GCP n'a pas été redéployée depuis ces merges** : exports, session 7j, extraction PII et MCP durci ne seront effectifs en prod qu'après `git pull` + `docker compose up -d --build` sur la VM (manuel).

Avant : Phase 2 (identité visuelle Pulsar-graph + audit) et Phase 1 (MVP complet, flow login → création → signature → attestation → publication).

---

## PRs ouvertes

_Aucune._ Toutes les PRs #135-#144 ont été mergées le 2026-07-19 (imports, citations IA, session 7j, export docx, métadonnées PII, deps sécurité, durcissement MCP, extension MV3, page /developers, docs). Suite des merges vérifiée sur main : backend 182/182 tests, frontend check/build OK. Les 11 vieilles PRs Dependabot < #100 ont été fermées le même jour (remplacées par le patch groupé #140 + overrides pnpm).

> Mergées avant : #121-#134 (exports, imports, citations IA, graph colors, etc.), #116-#120 (infra GCP + LLM extract), #112-#115 (waitlist, seed & claim, MCP, adoption).

> _Quand cette section est vide, plus rien n'est en attente côté review humaine._

---

## URLs production

- **Frontend** : https://filum-eight.vercel.app
- **Backend** : https://philum-api.duckdns.org (GCP e2-micro + Caddy, cf. ADR-028)
- **API docs** : https://philum-api.duckdns.org/api/v1/docs
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau
- **Ancien backend Railway** : https://filum-production-07bb.up.railway.app — décommissionnable

---

## Stack effective

**Backend** : Python 3.12 · FastAPI async · SQLAlchemy 2.x async · Alembic · PostgreSQL (Supabase, Session pooler 5432) · Crypto Ed25519 + AES-GCM + HS256 (PyJWT) · Pillow (OG images) · slowapi (rate limit) · pytest (~70 tests) · Hébergé sur GCP e2-micro (Docker Compose + Caddy TLS).

**Frontend** : SvelteKit 2 · Svelte 5 (runes) · TypeScript · Tailwind · D3 v7 (graphe) · OGL (WebGL hero, lazy) · Vercel · pnpm 10 pinné · Logo Philum v1 (Pulsar-graph CB12 + Z13 palette).

**Analytics** : dbt-core sur DuckDB (job `dbt compile` en CI).

**Architecture OAuth** : Frontend → proxy SvelteKit `/api/[...path]` → Backend (cookies first-party). Backend lit `X-Filum-Public-Origin` (set par proxy) pour construire `redirect_uri` (cf. ADR-025).

---

## CI (workflows GitHub Actions)

3 workflows : `ci.yml`, `analytics.yml`, `security.yml`. Jobs (~16 total) : Lint/Test/Type-Check Backend + Frontend, Build Frontend, Analytics (dbt compile), Security Scan (Trivy), Static Analysis (Bandit), Vulnerability Check (Safety), Secrets Detection (TruffleHog), Dependency Review, CI Summary, Vercel preview.

Toutes les actions bumpées en juin 2026 (`pnpm v6`, `setup-python v6`, `checkout v6`).

---

## Variables d'environnement (production GCP)

Fichier `~/filum/infra/oracle/.env` sur la VM (modèle : `infra/oracle/.env.example`) :

```
database_url           = postgresql://postgres.<ref>:<pwd>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://philum-api.duckdns.org
google_redirect_uri    = https://philum-api.duckdns.org/api/v1/auth/google/callback
cors_origins           = ["https://filum-eight.vercel.app"]
google_client_id       = <Google OAuth Client ID>
google_client_secret   = <Google OAuth Client secret>
API_DOMAIN             = philum-api.duckdns.org   # utilisée par Caddy (TLS)
```

⚠️ **Toutes en lowercase** (ADR-010 — pydantic-settings `case_sensitive=True`), sauf `API_DOMAIN` (consommée par Caddy, pas par pydantic). ⚠️ Supabase : **Session pooler port 5432**, jamais le Transaction pooler 6543 (casse asyncpg).

Vercel : `BACKEND_URL=https://philum-api.duckdns.org` (env var serverless, jamais exposée navigateur).

---

## Bugs latents (non bloquants)

| Bug | Sévérité | Localisation |
|---|---|---|
| `impact_factor` toujours `null` | Faible | OpenAlex retiré, pas de fallback. Soit rebrancher une source, soit retirer le champ UI. |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5. |
| Wayback queue durability | Moyenne | `asyncio.create_task` perdu au restart du container backend. Cf. F5 dans `13-audit-2026-05-26-followups.md`. |
| Pas de domaine custom | Feature | Brancher `philum.app` quand 1er ambassadeur prêt. |

---

## Prochaines étapes (par ordre d'impact/coût)

> **Roadmap consolidée et priorisée** : [`.docs/19-roadmap-2026-07.md`](./.docs/19-roadmap-2026-07.md). Plan d'audit détaillé : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md). Comptes plateformes liés : [`.docs/18-linked-accounts.md`](./.docs/18-linked-accounts.md).

**Immédiat** (post-merges du 2026-07-19)
- **P0 — Redéployer la VM GCP** (`git pull` + `docker compose -f docker-compose.micro.yml up -d --build`) : exports (le « seul PDF marche » venait de là — l'endpoint /export renvoie 404 en prod), session 7j, extraction PII, MCP durci.
- **Merger #135 avant #136**, puis retarget la base de #136 sur main (piège des PRs empilées).
- **Alerte budget 1 € sur GCP** (Billing → Budgets & alerts) si pas déjà en place — filet de sécurité, pas de plafond natif.
- **Décommissionner Railway** : supprimer le service + retirer l'ancienne redirect URI Railway du client OAuth Google.

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
- **ADR-028** : hébergement GCP e2-micro always-free + Supabase (post-Railway)

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
6. Vérifier l'état avec : `git log --oneline -10`, `wsl gh pr list`, `curl https://philum-api.duckdns.org/health`.
7. Choisir une tâche dans « Prochaines étapes » ci-dessus.
8. Branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite.

---

## Mettre à jour ce fichier

Quand la session apporte un changement significatif (PR mergée, phase qui change, URL prod modifiée, nouvelle ADR), **éditer la section pertinente** et bumper la date en haut. Pour les détails de la session (commits, root causes, bugs résolus), **écrire dans `CHANGELOG.md`** — pas ici.
