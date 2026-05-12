# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-12** — session « MVP merge + déploiement Railway »

---

## Phase courante

**Phase 1 — MVP déployé.** Backend live sur Railway, frontend non déployé.

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

---

## Variables d'environnement (Railway, production)

```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = http://localhost:5173    (à updater quand frontend déployé)
backend_base_url       = https://filum-production-07bb.up.railway.app
cors_origins           = ["http://localhost:5173"]
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
| Frontend non déployé | Feature | Choisir Vercel ou Netlify, pointer sur `apps/frontend/` |
| Pas de domaine custom | Feature | Brancher `filum.app` quand prêt |

---

## Prochaines étapes (par ordre logique)

0. **Itération 2 livrée** (ADR-017) : nouveau logo arbre+graphe, indicateurs typés + extraits (table `source_excerpts`), conflits d'intérêt déclarés, refonte cartographie (labels auteurs, seuils de zoom, plein écran), panneau de détail ancré au nœud, SSR + JSON-LD sur la fiche publique (référencement Google + GEO Perplexity/SearchGPT/Claude).
1. **OAuth Google** : credentials Google Cloud Console → variables `google_client_id` / `google_client_secret` / `google_redirect_uri` (lowercase) dans Railway. Côté frontend, basculer le cookie `filum_session` en `samesite=none` pour cross-origin Vercel↔Railway.
2. **Tester flow auth bout-en-bout** : login → callback → cookie session → /api/v1/auth/me
3. **Implémenter `apps/backend/app/extractors/`** : module d'extraction URL → métadonnées (titre, auteur, date, snapshot Wayback). C'est la pierre angulaire du produit.
4. **Page création de fiche** : `/dashboard/new` (formulaire + UI ajout sources + définition manuelle des `parent_source_id`)
5. **Refactor `crypto/signing.py`** : déplacer `SigningService` depuis `hashing.py` ou supprimer le stub
6. **Fix deps eslint frontend** : ajouter les paquets manquants, retirer `|| true`
7. **Réécrire un test composant Svelte 5** : utiliser `createRawSnippet` ou l'API actuelle de testing-library/svelte
8. **Export PDF** d'une fiche
9. **Mode privé + intégrations Zotero / Obsidian / Notion** (cf. `.docs/09-private-mode-and-integrations.md`)

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
