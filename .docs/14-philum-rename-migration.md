# Renommage Filum → Philum — Plan de migration

> Document d'accompagnement de la PR `feat/rename-philum`.
> **État de cette PR : Phase 1 uniquement (texte visible frontend).**
> Phases 2-4 documentées ci-dessous pour exécution séparée.

## Pourquoi ce document

Le scan exhaustif a identifié **429 occurrences sur 83 fichiers** au début de l'opération. Les modifier toutes en une seule PR aurait :

- Couplé fortement frontend, backend, infra, doc dans un seul gros diff non-reviewable
- Cassé la prod lors du déploiement partiel (OAuth, cookies, env vars, package names, Vercel subdomain, Railway service, etc.)
- Empêché de tester les étapes en isolation

La stratégie retenue : **4 phases incrémentales**, mergeables séparément, sans casser la prod entre chaque phase.

## Phase 1 — Texte visible frontend (CETTE PR)

**Statut : ✅ Réalisé, prêt à merger.**

Renommages appliqués (uniquement le texte visible à l'utilisateur final, jamais d'URL/identifiant/clé) :

| Fichier | Type de changement |
|---|---|
| `apps/frontend/src/lib/components/Logo.svelte` | Commentaire JSDoc |
| `apps/frontend/src/lib/components/HeroPulsar.svelte` | `aria-label` SVG fallback |
| `apps/frontend/src/routes/+layout.svelte` | Texte header + footer copyright |
| `apps/frontend/src/routes/+page.svelte` | `<title>`, meta description, body landing |
| `apps/frontend/src/routes/about/+page.svelte` | Toutes les occurrences visibles (12) |
| `apps/frontend/src/routes/features/+page.svelte` | Toutes les occurrences visibles (7) |
| `apps/frontend/src/routes/security/+page.svelte` | Toutes les occurrences visibles (6) |
| `apps/frontend/src/routes/roadmap/+page.svelte` | Toutes les occurrences visibles (4) |
| `apps/frontend/src/routes/privacy/+page.svelte` | Toutes les occurrences visibles (3 — URL conservée) |
| `apps/frontend/src/routes/+error.svelte` | `<title>` (URL issue conservée) |
| `apps/frontend/src/routes/@[username]/+page.svelte` | `<title>` |
| `apps/frontend/src/routes/@[creator]/[card]/+page.svelte` | `<title>`, JSON-LD `name`, `og:site_name` |
| `apps/frontend/src/routes/auth/callback/+page.svelte` | `<title>` |
| `apps/frontend/src/routes/dashboard/+page.svelte` | `<title>` |
| `apps/frontend/src/routes/dashboard/new/+page.svelte` | `<title>` |
| `apps/frontend/src/routes/dashboard/new/[card_id]/sources/+page.svelte` | `<title>` + texte body |
| `apps/frontend/src/routes/sandbox/logo/+page.svelte` | Comments + sandbox title |

**Strict no-go pour Phase 1** (occurrences `Filum`/`filum` intentionnellement non touchées) :

- `https://github.com/Mathias-PP/filum` (URL du repo — non renommé sur GitHub)
- `https://github.com/Mathias-PP/filum/issues`
- `https://filum-eight.vercel.app/*` (URL de déploiement Vercel — subdomain non renommé)
- `https://filum-api.up.railway.app` (URL backend Railway)
- `'filum-theme'` (clé `localStorage` — renommer invaliderait les préférences thème de tous les users existants)
- `filum_oauth_state` (nom de cookie OAuth — backend set/read coordonné)
- `x-filum-public-origin` (header HTTP custom — backend read coordonné)
- `filum-frontend` (nom du package npm)

**Aucun impact runtime, aucune migration de données, aucun déploiement coordonné nécessaire.** Cette PR peut être mergée et déployée immédiatement.

## Phase 2 — Documentation (PR à créer)

Renommage texte des fichiers `.md` et meta-config :

```
README.md (13 occurrences)
.docs/00-vision.md (8)
.docs/01-product-spec.md (11)
.docs/02-tech-architecture.md (3)
.docs/03-data-model.md (2)
.docs/04-api-design.md (5)
.docs/05-design-system.md (1)
.docs/06-roadmap.md (3)
.docs/07-open-questions.md (6)
.docs/08-glossary.md (33)
.docs/09-private-mode-and-integrations.md (12)
.docs/10-mvp-completion-plan.md (9)
.docs/11-critique-and-improvements.md (5)
.docs/12-next-steps.md (15)
.docs/12-ui-redesign-execution-plan.md (3)
.docs/13-audit-2026-05-26-followups.md (2)
DECISIONS.md (48 — attention : ADR-021 documente précisément ce rename)
STATE.md (20+)
CHANGELOG.md (2)
SETUP.md (8)
SECURITY.md (2)
CONTRIBUTING.md (4)
CLAUDE.md (4)
AGENTS.md (2)
agent/*.md
.github/ISSUE_TEMPLATE/bug_report.yml (1)
```

**Approche recommandée** : `sed -i 's/Filum/Philum/g'` global sur ces fichiers, suivi d'une revue manuelle de DECISIONS.md (ADR-021 décrit le rename — paraphrase nécessaire pour éviter de présenter le rename comme "Filum → Filum") et de glossary.md (entrée étymologique « Filum = fil en latin » qui doit devenir « Philum ⟵ Filum = fil en latin »).

**Risque** : aucun (texte uniquement).
**Déploiement** : nul (docs ne sont pas servies).

## Phase 3 — Identifiants et infra applicative (PR à créer)

Renommages qui nécessitent **changements coordonnés** mais sans migration de données :

### 3a. localStorage key
- `apps/frontend/src/app.html` ligne 15 : `localStorage.getItem('filum-theme')` → `'philum-theme'`
- `apps/frontend/src/lib/stores/theme.ts` ligne 5 : `STORAGE_KEY = 'filum-theme'` → `'philum-theme'`
- **Impact** : les préférences thème de tous les users existants sont invalidées (revient à light mode au prochain chargement). À mitiger via lecture compat : essayer d'abord `'philum-theme'`, fallback `'filum-theme'`, et migrer à l'écriture.

### 3b. Package npm
- `apps/frontend/package.json` : `"name": "filum-frontend"` → `"philum-frontend"`
- **Impact** : aucun runtime, mais ça touche `pnpm-lock.yaml` (probablement déjà CI-prettier-cassé sur les PRs Dependabot existantes — cf. STATE 2026-05-26 audit).

### 3c. Comments / variables internes
- `apps/frontend/src/routes/api/[...path]/+server.ts` ligne 61 : commentaire `X-Filum-Public-Origin` peut être renommé en `X-Philum-Public-Origin` **uniquement si on renomme le header dans le backend en même temps** (cf. Phase 4a). Si on garde le header legacy `X-Filum-Public-Origin`, garder le commentaire intact.

### 3d. Analytics dbt
- `apps/analytics/dbt_project.yml` : `name: 'filum'` → `'philum'`
- `apps/analytics/profiles.yml` : références au profil `filum`
- `apps/analytics/models/sources.yml` : références au schéma
- **Impact** : nul en prod (analytics DuckDB local pour l'instant), mais nécessite de re-run `dbt run` après merge.

**Stratégie de merge** : 3a + 3c en une PR (frontend coordonné). 3b en une PR isolée (touche lockfile, Dependabot peut casser). 3d en une PR à part avec rerun dbt en check.

## Phase 4 — Backend + infra critique (PR à créer en DERNIER)

C'est la phase qui demande coordination prod et qui peut casser l'auth/cookies/OAuth si mal exécutée.

### 4a. Cookies et headers backend
- `filum_session` cookie name (FastAPI session middleware)
- `filum_oauth_state` cookie name (OAuth flow)
- `X-Filum-Public-Origin` header (proxy SvelteKit → backend)
- **Migration nécessaire** :
  - Backend lit les DEUX noms (legacy `filum_*` + nouveau `philum_*`) pendant une période de transition
  - Backend set les NOUVEAUX noms à partir du déploiement
  - Après ~30 jours, supprimer la lecture legacy
  - Sinon : invalidation forcée de toutes les sessions le jour J (acceptable seulement si user base très petite — c'est le cas en pré-MVP, donc peut-être plus simple)

### 4b. Env vars backend (`apps/backend/app/core/config.py`)
Liste des env vars contenant "filum" (à vérifier par grep) :
```
app_name = "Filum API"  # safe à renommer
frontend_base_url
# pas d'env var explicitement "filum_*" je crois — à confirmer
```
- **Migration** : revoir `.env.example`, mettre à jour Railway env vars en parallèle du déploiement.

### 4c. Domain Vercel + Railway
- Vercel subdomain : `filum-eight.vercel.app` → `philum-eight.vercel.app` (ou domaine custom `philum.app`)
- Railway service : `filum-production-07bb.up.railway.app` → similaire ou domaine custom
- **Migration** :
  - Réserver nouveau subdomain Vercel
  - Mettre à jour env var `frontend_base_url` côté Railway
  - Mettre à jour `Authorized redirect URI` côté GCP OAuth Client
  - Tester OAuth bout-en-bout
  - Communiquer aux users (si applicable)
  - Garder l'ancien subdomain en redirect 301 vers le nouveau pendant ~6 mois
  - URLs dans le code frontend (`https://filum-eight.vercel.app/*`) mises à jour en simultané

### 4d. Repo GitHub
- Renommer `Mathias-PP/filum` → `Mathias-PP/philum` via GitHub UI
- GitHub crée automatiquement les redirects pour les anciennes URLs
- Mettre à jour `git remote set-url origin` chez tous les contributeurs
- Mettre à jour les URLs dans le code (`https://github.com/Mathias-PP/filum/...`)

### 4e. Backend package
- `apps/backend/pyproject.toml` : `name = "filum"` (ou similaire)
- `apps/backend/app/` : potentiellement renommer le package Python mais pas obligatoire (le path import est court).

### 4f. Tests
- `apps/backend/tests/integration/test_oauth_callback.py` (7 occurrences) : asserts sur cookies/headers à mettre à jour
- `apps/backend/tests/unit/test_auth.py` (6) : idem
- `apps/backend/tests/integration/test_auth_endpoints.py` (3) : idem
- À faire en même temps que 4a.

### 4g. Docker / scripts / Makefile
- `docker-compose.yml`, `docker-compose.dev.yml`, `infra/postgres/docker-compose*.yml` : noms de services/containers
- `Makefile` : commandes
- `scripts/*.sh` : URLs Railway, noms de services
- À faire en simultané du déploiement Phase 4c.

## Ordre de merge recommandé

1. **Phase 1** (cette PR) — immédiat, aucun risque
2. **Phase 2** (docs) — semaine suivante, aucun risque
3. **Phase 3a-3c** (frontend identifiers) — quand prêt, risque minimal (théming peut être migré côté JS)
4. **Phase 3d** (dbt analytics) — indépendant, à faire avant utilisation prod
5. **Phase 4** (backend + infra) — **coordonnée avec un déploiement**, idéalement combinée à l'achat/réservation du domaine `philum.app` si on pivote vers un domaine custom

## Notes opérationnelles

- L'ADR-021 (DECISIONS.md) qui documente déjà la décision Filum → Philum devra être augmentée pour pointer vers ce document de migration.
- Quand toutes les phases sont terminées, ce document peut être archivé (déplacer vers `.docs/archive/` ou suffixer `-DONE`).
- La sandbox `/sandbox/logo` peut continuer d'utiliser indistinctement Filum/Philum pendant la transition — c'est un outil interne.

## Lien avec PR #84 (sandbox/logo iterations)

La PR #84 (`feat/hero-design-iter`) en cours touche fortement `apps/frontend/src/routes/sandbox/logo/+page.svelte`. Cette PR (`feat/rename-philum`) modifie le titre et 2 commentaires dans le même fichier sur sa version main.

**Ordre de merge recommandé** :
1. Merger PR #84 d'abord (logo work).
2. Puis rebaser `feat/rename-philum` sur main.
3. Conflit attendu uniquement sur la version sandbox/logo : trivial à résoudre (les 3 lignes Filum→Philum à reporter sur la nouvelle version du fichier).

Alternative : merger Phase 1 (cette PR) avant PR #84 — le conflit sera dans l'autre sens mais aussi trivial.
