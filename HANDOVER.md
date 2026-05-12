# Prompt de passation — Prochain agent IA

Tu prends la suite du développement du projet **Filum** (infrastructure ouverte de provenance et de filiation pour le contenu numérique). Lis dans l'ordre avant d'agir :

1. [`AGENTS.md`](./AGENTS.md) — règles essentielles (3 min)
2. [`STATE.md`](./STATE.md) — état du projet à l'instant T (5 min)
3. [`DECISIONS.md`](./DECISIONS.md) — décisions techniques passées (5 min)
4. `.docs/01-product-spec.md` — features et scénarios (10 min)
5. `.docs/02-tech-architecture.md` — architecture (5 min)

---

## Mission prioritaire

**Rendre la CI entièrement verte sur `feat/frontend-sveltekit-mvp`**, puis **préparer le merge des branches `feat/*` vers `main`**.

### Pourquoi

Le projet est en phase MVP. Deux branches `feat/` existent :
- `feat/infrastructure-and-backend-mvp` (backend + CI/CD)
- `feat/frontend-sveltekit-mvp` (frontend + derniers fixes CI)

Le build frontend est rouge. Tant qu'il ne passe pas, on ne peut pas merger proprement.

---

## État CI actuel

Sur `feat/frontend-sveltekit-mvp` :
- ✅ Security Scan
- ✅ Lint Backend (ruff)
- ✅ Type Check Backend (mypy)
- ✅ Lint Frontend (eslint + prettier, `|| true`)
- ✅ Test Backend (38 pytest)
- ✅ Test Frontend (vitest, `|| true`)
- ✅ Analytics Check (dbt compile)
- ❌ **Build Frontend** (pnpm run build échoue)

---

## Étapes détaillées

### 1. Debug Build Frontend

Le build échoue sur `pnpm run build` (pas sur `pnpm install`). Causes possibles :
- Dépendances manquantes dans la CI (ex: `@sveltejs/adapter-vercel` non installé)
- Erreur TypeScript non catchée par `pnpm run check`
- Problème de config Vite/SvelteKit

**Fichiers à examiner :**
- `apps/frontend/package.json` — scripts build, adapter
- `apps/frontend/svelte.config.js` — config SvelteKit
- `apps/frontend/vite.config.ts` — config Vite
- `.github/workflows/ci.yml` — job `build-frontend` (lignes 207-245)

**Commande pour reproduire localement :**
```bash
cd apps/frontend
pnpm install
pnpm run build
```

### 2. Une fois le build vert

Appliquer le même commit SHA au build-frontend à `feat/infrastructure-and-backend-mvp` (cherry-pick).

### 3. Merge des branches feat/* vers main

Stratégie recommandée : **squash merge** (un commit propre par branche).

```bash
git checkout main
git merge --squash feat/infrastructure-and-backend-mvp
git commit -m "feat: backend MVP with FastAPI, auth, crypto, CI/CD"
git merge --squash feat/frontend-sveltekit-mvp
git commit -m "feat: frontend MVP with SvelteKit, design system, auth pages"
git push origin main
```

### 4. Prochaines features (après merge)

1. **OAuth Google callback fonctionnel** : l'endpoint existe (`GET /api/v1/auth/google/callback`) mais le callback avec échange de token via httpx n'est pas testable sans credentials Google. Vérifier le flow complet.
2. **Graphe D3.js** sur la page publique `apps/frontend/src/routes/[creator]/[card]/+page.svelte`
3. **Page création de fiche** `apps/frontend/src/routes/dashboard/new/+page.svelte`
4. **Export PDF**

---

## Pièges connus

### pnpm 11 — `ERR_PNPM_IGNORED_BUILDS`
- `onlyBuiltDependencies` dans `package.json` ignoré par pnpm 11 en CI
- `.pnpm-approve-builds.json` ignoré aussi
- **Workaround** : `pnpm config set onlyBuiltDependencies` + `|| true` sur `pnpm install`
- Toute nouvelle job CI frontend doit appliquer ce pattern

### pydantic-settings `case_sensitive=True`
- Les variables d'environnement doivent être en **lowercase** (ex: `database_url`, pas `DATABASE_URL`)
- Applicable partout : `.env`, CI `env:`, `conftest.py`
- `SettingsConfigDict(case_sensitive=True)` dans `apps/backend/app/core/config.py`

### Tests DB — `Base.metadata.create_all`
- Ne crée rien si les modèles ne sont **pas importés** avant l'appel
- `conftest.py` doit importer explicitement `app.models.user`, `app.models.biblio_card`, etc.
- Les tests utilisent SQLite + aiosqlite, pas PostgreSQL

### Remote Git
- L'ancien remote `filum_project` existe encore (push possible mais redirigé)
- Le bon remote est `https://github.com/Mathias-PP/filum.git`
- Vérifier avec `git remote -v`

---

## Tests à exécuter avant toute action

```bash
# Backend
cd apps/backend
uv run pytest tests/ -v --tb=short
uv run ruff check app/
uv run mypy app/ --ignore-missing-imports

# Frontend
cd apps/frontend
pnpm run lint
pnpm run check
pnpm run build
```

---

## Commandes Git utiles

```bash
# Voir les branches
git branch -a

# Voir les commits récents
git log --oneline -20

# Cherry-pick d'un fix d'une branche à l'autre
git checkout feat/infrastructure-and-backend-mvp
git cherry-pick <commit-sha>
git push origin feat/infrastructure-and-backend-mvp
```

---

## Résumé des fichiers critiques

| Fichier | Pourquoi |
|---------|----------|
| `.github/workflows/ci.yml` | CI à débugger (build-frontend job) |
| `apps/frontend/package.json` | Scripts, dépendances, adapter |
| `apps/frontend/svelte.config.js` | Config build |
| `apps/backend/app/core/config.py` | `case_sensitive=True` |
| `apps/backend/app/services/auth.py` | AuthService (JWT, Google OAuth) |
| `apps/backend/tests/conftest.py` | Fixtures de test (pattern à suivre) |
| `apps/backend/tests/unit/test_auth.py` | 15 tests auth (exemple qualité attendue) |
| `STATE.md` | Document vivant — le mettre à jour en fin de session |
| `DECISIONS.md` | Journal ADR — ajouter toute décision technique |
| `CHANGELOG.md` | Log des changements |

---

*Bon courage ! Le projet est bien structuré, la CI est à 7/8, les 38 tests passent. Le dernier push est `cc9aa87` sur `feat/frontend-sveltekit-mvp`.*
