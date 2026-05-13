# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-13** — session « P0 seed patch, sources non-académiques, logo circulaire, refonte noeud central du graphe »

---

## Phase courante

**Phase 1 — MVP déployé.** Backend live sur Railway, frontend live sur Vercel, fiche démo publique en SSR + JSON-LD.

---

## URLs

- **Repo** : https://github.com/Mathias-PP/filum
- **Backend prod** : https://filum-production-07bb.up.railway.app
  - `/health` → `{"status":"ok","version":"0.1.0"}`
  - `/health/database` → `{"status":"ok","database":"connected"}`
  - `/api/v1/docs` → Swagger UI
- **Frontend prod** : https://filum-eight.vercel.app
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau (graphe D3 interactif, 14 sources neurosciences, 6 arêtes de citation)

---

## Branches Git

| Branche | État |
|---|---|
| `main` | Branche unique. Tout est mergé, les feature branches MVP ont été supprimées. |

Le repo a été simplifié après le squash-merge de la PR #1 (« feat: MVP — backend FastAPI + frontend SvelteKit + CI verte »).

---

## CI

8/8 jobs verts sur `main` :

- Security Scan (Trivy SARIF, TruffleHog sur PR uniquement)
- Lint Backend (ruff)
- Type Check Backend (mypy, 0 erreur)
- Test Backend (41 tests pytest, 100% pass)
- Lint Frontend (eslint + prettier, **masqué par `|| true`** — voir follow-ups)
- Test Frontend (vitest avec `passWithNoTests: true`)
- Build Frontend (vite, `--frozen-lockfile`, pnpm 10 pinned)
- Analytics Check (dbt compile)

Workflow `cd.yml` supprimé : Railway déploie en natif via son intégration GitHub (cf. ADR-015).

---

## Stack effective déployée

### Backend
- Python 3.12 + FastAPI async + SQLAlchemy 2.x async + Alembic
- PostgreSQL (Railway plugin, lié via `${{Postgres.DATABASE_URL}}`)
- Crypto : Ed25519 + AES-GCM + HS256 (PyJWT, plus de python-jose, cf. ADR-014)
- Models : User, BiblioCard, Source, AuditEvent
- API REST sous `/api/v1/` : auth, cards, sources, users
- Migrations Alembic exécutées au boot dans le `CMD` Docker
- 41 tests (38 unit + 3 integration endpoints)

### Frontend
- SvelteKit 2 + Svelte 5 + TypeScript + Tailwind, déployé sur Vercel
- pnpm 10.33.4 pinned via `packageManager` (cf. ADR-013)
- Design system : Button, Input, Card, Avatar, Badge, Alert, SourceTypeBadge, SourceGraph, SourceDetailPanel
- Stores : auth, cards
- Routes : home, dashboard, public card (avec graphe D3), user profile
- D3 v7 (force-directed) + utilitaire `lib/utils/source-colors.ts` (single source of truth des couleurs de type de source)
- API base URL pilotée par `PUBLIC_API_BASE_URL` (env Vercel)

### Analytics
- dbt-core sur DuckDB (job `dbt compile` en CI)

---

## Décisions techniques récentes (post-merge)

Voir `DECISIONS.md` pour le détail :

- **ADR-013** : pin pnpm 10 (les workarounds pnpm 11 dégagent)
- **ADR-014** : migration `python-jose` → `PyJWT` (suppression CVE ecdsa Minerva)
- **ADR-015** : déploiement Railway via intégration native GitHub (pas de workflow CD)
- **ADR-016** : graphe interactif D3.js + `Source.parent_source_id` pour le citation graph (la fiche publique reflète enfin la promesse "wow" de la vision)
- **ADR-017** : itération 2 — indicateurs typés (citations, IF, abonnés, vues), table `source_excerpts`, conflits d'intérêt déclarés, SSR + JSON-LD sur la fiche publique, panneau de détail ancré au nœud, renommage Pivot → Source clé

---

## Variables d'environnement (Railway, production)

```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://filum-production-07bb.up.railway.app
cors_origins           = ["https://filum-eight.vercel.app","http://localhost:5173"]
debug                  = false
```

⚠️ **Toutes en lowercase** (ADR-010, `case_sensitive=True` dans pydantic-settings).

Variables intentionnellement non configurées (defaults dans `config.py` suffisent) :
- `google_client_id`, `google_client_secret`, `google_redirect_uri` — OAuth non activé
- `wayback_api_key` — feature Wayback pas encore branchée
- `duckdb_path` — DuckDB n'est pas chargé dans le backend (analytics séparé)

---

## Bugs latents identifiés (non fixés)

| Bug | Sévérité | Localisation |
|---|---|---|
| `apps/backend/app/extractors/` vide | Bloquant pour la prochaine feature | Module à implémenter (URL → métadonnées) |
| `crypto/signing.py` = stub | Code smell | `SigningService` colocalisé dans `hashing.py` ; déplacer ou supprimer le stub |
| Deps eslint frontend manquantes | Lint masqué par `\|\| true` | Manque `@eslint/js`, `@typescript-eslint/*`, `eslint-plugin-svelte`, `svelte-eslint-parser`, `eslint-config-prettier` |
| Test composant Svelte 5 incompat | Bloquait check, supprimé | À réécrire avec API testing-library compatible Svelte 5 (Snippet vs string) |
| 8 warnings `state_referenced_locally` | Best-effort | Composants design system passent `$state` en argument sans closure |
| 6 erreurs ruff dans `alembic/versions/001_initial.py` | Cosmétique | CI ne lint pas `alembic/`, généré auto, `Union[X, None]` → `X \| None` |
| Pas de domaine custom | Feature | Brancher `filum.app` quand prêt |
| Cookie `samesite=lax` | Bloquant pour OAuth | Bascule `samesite=none + secure=True` quand OAuth Google sera branché (cf. `apps/backend/app/api/v1/endpoints/auth.py` 128-152) |
| ~~Seed démo : données itération 2 absentes~~ | **Résolu** | `_get_or_create_demo_card` ne fait plus early-return ; delete+recreate les sources à chaque run ; les excerpts/indicateurs/conflits sont donc rafraîchis. |

---

## État production vérifié (2026-05-13)

Vérifié par `curl` sur les URL prod, pas par lecture des docs :

- ✅ Backend `/health` → 200 OK, version 0.1.0
- ✅ API `/api/v1/@example/memoire-et-cerveau` → 200, 16 sources (dont 2 non-académiques), signature Ed25519 présente
- ✅ Migration 004 **appliquée** : les nouveaux champs (`citations_count`, `subscribers_count`, `views_count`, `impact_factor`, `conflict_of_interest`, `excerpts[]`) sont bien sérialisés dans la réponse API
- ✅ Frontend SSR fonctionne : `<script type="application/ld+json">` présent dans le HTML statique, meta `og:title`/`og:description` présents
- ✅ **Seed P0 résolu** : `_get_or_create_demo_card` ne fait plus early-return. Les sources sont delete+recreate à chaque run, les nouveaux champs (excerpts, conflits, indicateurs) sont rafraîchis, et 2 nouvelles sources non-académiques sont ajoutées (documentaire NOVA + dessin Cajal). La fiche démo prod est re-signée à chaque run du seed.

---

## Prochaines étapes par priorité (basé sur l'état prod vérifié)

### P0 — ✅ Résolu (seed démo rafraîchi)

Le seed ne fait plus early-return : les sources sont recréées, les champs itération 2 (excerpts, conflits, indicateurs) sont rafraîchis, 2 nouvelles sources non-académiques ajoutées. La fiche est re-signée à chaque run (idempotent).

### P1 — Vision produit (sans ça, Filum reste un démonstrateur)

2. **Implémenter `apps/backend/app/extractors/` (actuellement vide).** Module d'extraction URL → métadonnées (titre, auteur, date, snapshot Wayback, et idéalement `citations_count`/`impact_factor` via Crossref / OpenAlex pour le peer-reviewed). Pierre angulaire annoncée depuis l'itération 1. Sans extracteur, aucun créateur ne peut ajouter de fiche sérieuse à grande échelle.
3. **Page `/dashboard/new` : création de fiche.** Aujourd'hui `apps/frontend/src/routes/dashboard/` ne contient qu'un `+page.svelte` (vue d'ensemble). Aucune UI pour créer une fiche → seul un seed Python permet de publier. Bloquant pour onboarder un premier vrai créateur (autre que Mathias).

### P2 — Auth / multi-utilisateur

4. **OAuth Google end-to-end.** Crédentials Google Cloud Console → variables `google_client_id` / `google_client_secret` / `google_redirect_uri` (lowercase) dans Railway. Côté backend, basculer les cookies session de `samesite=lax` → `samesite=none + secure=True` (cf. `apps/backend/app/api/v1/endpoints/auth.py` ~128-152) pour cross-origin Vercel ↔ Railway. Sans ça, impossible d'onboarder un utilisateur tiers.
5. **Tester le flow auth bout-en-bout** une fois OAuth branché : login → callback → cookie session → `/api/v1/auth/me`.

### P3 — Qualité interne (dette dormante)

6. **CI frontend lint réactivé.** `.github/workflows/ci.yml` lignes 131-138 contiennent encore `pnpm run lint || true` et `continue-on-error: true`. Le lint frontend est de facto désactivé. Ajouter les déps eslint manquantes (`@eslint/js`, `@typescript-eslint/*`, `eslint-plugin-svelte`, `svelte-eslint-parser`, `eslint-config-prettier`) et retirer les `|| true`.
7. **Nettoyer `crypto/signing.py`.** Le fichier est aujourd'hui un simple re-export depuis `hashing.py` (3 lignes). Soit déplacer `SigningService` ici, soit supprimer le shim.
8. **Réécrire un test composant Svelte 5.** Le test composant a été supprimé à l'itération 1 (incompatibilité Svelte 5). Le réécrire avec l'API courante `testing-library/svelte` (Snippet vs string).
9. **Nettoyage `authority_level`.** La colonne reste en base et est sérialisée par l'API, mais l'UI itération 2 ne l'utilise plus (remplacée par les chips d'indicateurs typés). Choisir : (a) la retirer du schéma + migration de drop, (b) la garder pour rétrocompat et documenter qu'elle est "legacy / non-affichée".

### P4 — Ouverture produit

10. **Mode privé + intégrations Zotero / Obsidian / Notion** (spec déjà écrite : `.docs/09-private-mode-and-integrations.md`). Repositionne Filum en compagnon plutôt qu'en concurrent.
11. **Domaine custom `filum.app`** côté Vercel et Railway.
12. **Export PDF** d'une fiche signée.

---

## Commandes utiles

```bash
# Backend local
cd apps/backend
uv sync --all-extras
uv run uvicorn app.main:app --reload                 # dev server
uv run pytest tests/ -v                              # tous les tests
uv run alembic upgrade head                          # appliquer migrations
uv run ruff check app/ && uv run mypy app/ --ignore-missing-imports

# Frontend local
cd apps/frontend
pnpm install --frozen-lockfile
pnpm run dev                                         # dev server
pnpm run check                                       # type check
pnpm run build                                       # production build

# Logs Railway
# → dashboard https://railway.com/project/<id>
# → service backend → Logs

# Voir les runs CI
wsl gh run list --branch main --limit 5

# Re-trigger CI (push vide)
git commit --allow-empty -m "ci: retrigger" && git push origin main
```

---

## Comment relancer une session avec un agent IA

Pour qu'un agent (Claude Code, Aider, etc.) reprenne efficacement :

1. Lire dans l'ordre : `README.md` → `STATE.md` (ce fichier) → `DECISIONS.md` → `.docs/01-product-spec.md` → `.docs/02-tech-architecture.md`
2. Vérifier l'état actuel :
   - `git log --oneline -10`
   - `wsl gh run list --branch main --limit 3`
   - `curl https://filum-production-07bb.up.railway.app/health`
3. Choisir une tâche dans « Prochaines étapes » ci-dessus
4. Travailler sur une branche `feat/<sujet>`, PR vers `main`, squash-merge
