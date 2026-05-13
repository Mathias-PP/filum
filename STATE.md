# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-13** — itération 3 complète (PR1 + PR2 mergées, CI verte) :
- PR1 : lint frontend enforced (ESLint 9 flat config, prettier bloquant), `signing.py` refactorisé, `dashboard/new` + `dashboard/new/[card_id]/sources` créés, vitest source-colors, `svelte-kit sync` ajouté en CI avant tests.
- PR2 : extracteur URL (`url_extractor.py` — Crossref + HTML scraping), endpoint `GET /sources/extract`, fix critique `asyncio.create_task` + session SQLAlchemy isolée (Wayback), guard SSRF (`HttpUrl` + scheme check), fix DOI regex, dead code supprimé.

---

## Phase courante

**Phase 1 — MVP déployé + itération 3 mergée.** Backend live sur Railway, frontend live sur Vercel, fiche démo publique avec graphe D3 18 sources, embranchement Y fonctionnel. Création de fiche disponible via `/dashboard/new`. Extracteur URL opérationnel côté backend (`GET /sources/extract`). CI entièrement enforced (0 `|| true`).

---

## URLs

- **Repo** : https://github.com/Mathias-PP/filum
- **Backend prod** : https://filum-production-07bb.up.railway.app
  - `/health` → `{"status":"ok","version":"0.1.0"}`
  - `/health/database` → `{"status":"ok","database":"connected"}`
  - `/api/v1/docs` → Swagger UI
- **Frontend prod** : https://filum-eight.vercel.app
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau (graphe D3 interactif, 18 sources neurosciences, 8 arêtes de citation, embranchement Y)

---

## Branches Git

| Branche | État |
|---|---|
| `main` | Branche unique. `feat/iteration-3-dashboard-ci` et `feat/iteration-3-extractor-wayback` mergées et supprimées. |

---

## CI

8/8 jobs verts sur `main` :

- Security Scan (Trivy SARIF, TruffleHog sur PR uniquement)
- Lint Backend (ruff)
- Type Check Backend (mypy, 0 erreur)
- Test Backend (41 tests pytest, 100% pass)
- Lint Frontend (eslint 9 flat config, prettier, **actif** depuis PR1 itération 3)
- Test Frontend (vitest, test source-colors 2/2)
- Build Frontend (vite, `--frozen-lockfile`, pnpm 10 pinned)
- Analytics Check (dbt compile)

Workflow `cd.yml` supprimé : Railway déploie en natif via son intégration GitHub (cf. ADR-015).

**Améliorations CI récentes (2026-05-13)** :
- Suppression du double `uv sync` dans `lint-backend` (le `--only-dev` initial était écrasé par `--all-extras`)
- Ajout de `.github/dependabot.yml` : mises à jour hebdo pip/npm, mensuelles GitHub Actions

---

## Stack effective déployée

### Backend
- Python 3.12 + FastAPI async + SQLAlchemy 2.x async + Alembic
- PostgreSQL (Railway plugin, lié via `${{Postgres.DATABASE_URL}}`)
- Crypto : Ed25519 + AES-GCM + HS256 (PyJWT, plus de python-jose, cf. ADR-014)
- Models : User, BiblioCard, Source, AuditEvent
- API REST sous `/api/v1/` : auth, cards, sources, users
- Migrations Alembic exécutées au boot dans le `CMD` Docker
- 40 tests (pytest — unit + integration)
- Extracteur URL : `app/extractors/url_extractor.py` (Crossref + HTML scraping)
- Endpoint `GET /api/v1/sources/extract` (no auth, best-effort metadata)

### Frontend
- SvelteKit 2 + Svelte 5 + TypeScript + Tailwind, déployé sur Vercel
- pnpm 10.33.4 pinned via `packageManager` (cf. ADR-013)
- Design system : Button, Input, Card, Avatar, Badge, Alert, SourceTypeBadge, SourceGraph, SourceDetailPanel
- Stores : auth, cards
- Routes : home, dashboard, public card (avec graphe D3), user profile, `/dashboard/new` (création fiche 2 étapes)
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
| ~~`apps/backend/app/extractors/` vide~~ | **Résolu** | `url_extractor.py` implémenté (Crossref + HTML scraping), endpoint `GET /sources/extract` |
| ~~`crypto/signing.py` = stub~~ | **Résolu** | SigningService + Canonicalizer déplacés dans `signing.py` |
| ~~Deps eslint frontend manquantes~~ | **Résolu** | 6 deps ajoutées, eslint 9 flat config, CI `\|\| true` retiré |
| ~~8 warnings `state_referenced_locally`~~ | **Résolu** | Composants convertis à `$derived()` / `$effect()` |
| Auth guard absent sur `/dashboard/new` | Moyen | Redirection si non connecté — non implémentée |
| Rate limiting absent sur `GET /sources/extract` | Moyen | slowapi déjà dep mais non branché |
| `impact_factor` toujours `null` | Faible | OpenAlex supprimé (dead code), pas de fallback |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5 |
| Cookie `samesite=lax` | Bloquant pour OAuth | Bascule `samesite=none + secure=True` quand OAuth Google sera branché (`auth.py` 128-152) |
| Pas de domaine custom | Feature | Brancher `filum.app` quand prêt |

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

2. ~~**Implémenter `apps/backend/app/extractors/`.**~~ **Fait (PR2 itération 3)** — `url_extractor.py` opérationnel (Crossref + HTML scraping), endpoint `GET /sources/extract`.
3. ~~**Page `/dashboard/new` : création de fiche.**~~ **Fait (PR1 itération 3)** — routes `dashboard/new` + `dashboard/new/[card_id]/sources` créées.
4. **Brancher l'extracteur dans le formulaire frontend.** Appeler `GET /sources/extract?url=...` au blur du champ URL pour pré-remplir titre, auteurs, date. Ajouter l'auth guard (redirect si non connecté) sur les routes `/dashboard/new`.

### P2 — Auth / multi-utilisateur

4. **OAuth Google end-to-end.** Crédentials Google Cloud Console → variables `google_client_id` / `google_client_secret` / `google_redirect_uri` (lowercase) dans Railway. Côté backend, basculer les cookies session de `samesite=lax` → `samesite=none + secure=True` (cf. `apps/backend/app/api/v1/endpoints/auth.py` ~128-152) pour cross-origin Vercel ↔ Railway. Sans ça, impossible d'onboarder un utilisateur tiers.
5. **Tester le flow auth bout-en-bout** une fois OAuth branché : login → callback → cookie session → `/api/v1/auth/me`.

### P3 — Qualité interne (dette dormante)

6. ~~**CI frontend lint réactivé.**~~ **Fait (PR1 itération 3).**
7. ~~**Nettoyer `crypto/signing.py`.**~~ **Fait (PR1 itération 3).**
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
