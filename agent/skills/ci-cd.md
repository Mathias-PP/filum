# Skill: CI/CD

> Quand l'utiliser : modifier un workflow GitHub Actions, débugger une CI rouge, ajouter un check, comprendre le pipeline de déploiement.

## Contexte

CI sur GitHub Actions, 8 jobs verts requis sur main. Déploiement Railway et Vercel auto sur push main (pas de workflow CD séparé, cf. ADR-015). Wait-for-CI activé sur Railway : il attend que GitHub Actions soit vert avant de déployer.

## Architecture CI

```
.github/workflows/
├── ci.yml          # 7 jobs : lint, type, test backend/frontend, build frontend, analytics
├── security.yml    # Trivy (SARIF) + TruffleHog (PR uniquement)
└── analytics.yml   # dbt compile (job dédié)
```

Pas de `cd.yml` (supprimé, ADR-015). Railway et Vercel déploient via leurs intégrations GitHub natives.

## Checklist d'exécution

### Pour ajouter un job CI

1. Modifier `.github/workflows/ci.yml`. Suivre le pattern existant.
2. Toujours `runs-on: ubuntu-latest`.
3. Pour Python : `astral-sh/setup-uv@v3` puis `uv sync`. **Pas** de double `uv sync` (cf. STATE.md).
4. Pour Node : `pnpm/action-setup@v4` (honore `packageManager` dans `package.json`), puis `pnpm install --frozen-lockfile`.
5. Pas de `|| true` (anti-pattern, masque les vrais bugs).
6. Tester localement l'équivalent avant de pousser.

### Pour débugger une CI rouge

```bash
gh run list --branch <ma-branche> --limit 5
gh run view <run-id>
gh run view <run-id> --log-failed
```

90% des cas sont dans [`../PITFALLS.md`](../PITFALLS.md) (section 1, 2, 3).

### Pour modifier un workflow

⚠️ Tout changement de workflow est sensible. Avant de pousser :
- `gh workflow view <name>` après push pour vérifier que les jobs sont parsés (cf. `PITFALLS.md` 3.1 : YAML invalide donne 0 jobs).
- Vérifier qu'aucune action référencée n'est fictive (cf. `PITFALLS.md` 3.2).
- Préférer pinner les actions à un SHA plutôt qu'à un tag (`actions/checkout@v4` OK, `actions/checkout@main` ❌).

### Re-trigger une CI sans changement

```bash
git commit --allow-empty -m "ci: retrigger"
git push origin <ma-branche>
```

### Si Railway crash-loop après push

1. Vérifier les logs Railway (dashboard).
2. 99% du temps : migration Alembic qui throw. Cf. `PITFALLS.md` 4.4.
3. La BDD n'est pas corrompue (DDL rollback atomique).
4. Pousser le fix, attendre le prochain build.
5. Si urgent : Railway permet un rollback manuel vers un build précédent dans le dashboard.

## Pièges spécifiques

- **YAML workflow_dispatch mal nesté** : 0 jobs, pas d'erreur visible. Cf. `PITFALLS.md` 3.1.
- **Action GitHub fictive** : LLM invente parfois. Vérifier sur le marketplace. Cf. `PITFALLS.md` 3.2.
- **`dependency-review-action` bloque sur CVE transitive non exploitable** : cf. ADR-014 (`python-jose` → `PyJWT`).
- **`|| true` qui masque** : interdit. Cf. `PITFALLS.md` 3.4.
- **Variables d'env CI en UPPERCASE** : silencieusement ignorées. Tout en lowercase. Cf. `PITFALLS.md` 1.6.
- **GitHub Actions quotas free tier** : 2000 min/mois. Si on monte, ajouter `paths-ignore` pour les changements doc-only.

## Fichiers à connaître

- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/analytics.yml`
- `.github/dependabot.yml` — mises à jour deps (pip hebdo, npm hebdo, GHA mensuel)
- `apps/backend/Dockerfile` — build Railway, `${PORT:-8000}` pour binding dynamique
- `infra/` — docker-compose dev

## Pour aller plus loin

- ADR-015 (Railway déploiement via intégration GitHub native)
- ADR-013 (pnpm 10 pinné via `packageManager`)
- ADR-014 (PyJWT — résolution dependency-review)
- [`../GIT_WORKFLOW.md`](../GIT_WORKFLOW.md) section « Anticipation : avant de pousser »
