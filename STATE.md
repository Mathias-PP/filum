# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-13** — **MVP complet !** Tous les jalons M1+M2+M3 sont terminés, l'OAuth Google est configuré en prod et fonctionnel. Le flow de bout en bout (login → création → publication → consultation publique) est opérationnel.

### PR #27 — MVP Polish (mergée)
- Navbar : avatar utilisateur avec dropdown (menu déroulant, lien dashboard, déconnexion)
- Landing page auth-aware : bouton "Continuer avec Google" remplacé par "Accéder au tableau de bord" quand connecté
- Page /about créée avec contenu complet
- Bannière bêta privée supprimée
- Description expandable (Lire la suite / Moins) sur fiches publiques
- Typage strict `data.user: User | null` dans layout + landing

### PR #28 — Card creation flow (en cours)
- **Nouvel endpoint** `GET /sources?card_id=...` : liste les sources d'une fiche
- **Sources page fix** : charge les sources existantes au montage (plus de liste vide au retour)
- **Publish fix** : ne bloque plus sur `archive_status=PENDING` (Wayback best-effort)
- Suppression du check PENDING dans `POST /cards/{id}/publish` (le publish ne doit pas dépendre du résultat Wayback)

### Bugs corrigés (itérations précédentes)
- Fix 404 en cliquant sur un brouillon depuis le dashboard
- Fix bouton retour étape 2 → étape 1
- Fix erreur "An error occurred" non explicite : handler HTTPException
- Ajout endpoint `DELETE /cards/{id}` + bouton suppression

### Jalons terminés
- **M1** — OAuth Google (backend + frontend, manque credentials humains)
- **M2** — Auth guard + extracteur URL branché
- **M3** — Rate limiting, logs structurés, backup documenté

Jalon M1 livré précédemment :
- Backend : endpoints `/auth/google/login` et `/auth/google/callback` complétés. State token CSRF en cookie HttpOnly. Échange code → id_token vérifié via Google JWKS (PyJWKClient). Création/retrouvage User. Cookie session avec samesite conditionnel (`lax` en debug, `none+secure` en prod). Génération paire Ed25519 chiffrée AES-GCM à la première connexion.
- Frontend : bouton « Continuer avec Google » sur `/` avec icône. Page `/auth/callback` qui hydrate le store auth. `credentials: 'include'` déjà présent dans le client API.
- Tests : 72 tests pytest (66 existants + 6 nouveaux). 1 test d'intégration callback mocké + tests unitaires state cookie.
- Aucune nouvelle dépendance ajoutée (PyJWT + httpx + cryptography existaient déjà).

Itérations précédentes :
- PR1 (itération 3) : lint frontend enforced (ESLint 9 flat config, prettier bloquant), `signing.py` refactorisé, `dashboard/new` + `dashboard/new/[card_id]/sources` créés, vitest source-colors, `svelte-kit sync` ajouté en CI avant tests.
- PR2 (itération 3) : extracteur URL (`url_extractor.py` — Crossref + HTML scraping), endpoint `GET /sources/extract`, fix critique `asyncio.create_task` + session SQLAlchemy isolée (Wayback), guard SSRF (`HttpUrl` + scheme check), fix DOI regex, dead code supprimé.

---

## Phase courante

**Phase 1 — MVP complet.** Tous les jalons M1+M2+M3 sont terminés. L'OAuth Google est configuré et fonctionnel (302 vers `accounts.google.com` avec le bon `client_id` et `redirect_uri`). Le flow login → création → publication → consultation publique peut être testé de bout en bout.

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

9/9 jobs verts sur `main` :

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
| ~~Auth guard absent sur `/dashboard*`~~ | **Résolu** | `+layout.ts` dans `/dashboard/` redirige vers `/` si non connecté |
| ~~Rate limiting absent sur `GET /sources/extract`~~ | **Résolu** | slowapi branché : 10 req/min sur `/sources/extract`, 20 req/h sur `POST /cards` |
| `impact_factor` toujours `null` | Faible | OpenAlex supprimé (dead code), pas de fallback |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5 |
| ~~Cookie `samesite=lax`~~ | **Résolu** | Bascule `samesite=none + secure=True` conditionnée sur `settings.debug` (PR jalon M1) |
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
4. ✅ **Brancher l'extracteur dans le formulaire frontend.** Appel `GET /sources/extract?url=...` au blur du champ URL en étape 2, pré-remplit titre + auteurs, spinner, silent fail.
5. ✅ **Auth guard `/dashboard*`.** `+layout.ts` redirige vers `/` si `parent().user` est null.
6. ✅ **Rate limiting sur `GET /sources/extract` et `POST /cards`.** slowapi branché (10 req/min, 20 req/h).
7. ✅ **Logs structurés.** Middleware request_id + durée + status.

### P2 — Auth / multi-utilisateur

4. ~~**OAuth Google end-to-end.**~~ **Fait (PR jalon M1)** — endpoints `/auth/google/login` et `/auth/google/callback` opérationnels, state CSRF en cookie, vérification id_token via JWKS, cookie samesite conditionnel. Reste la configuration humaine des credentials Google Cloud + Railway (hors scope agent).
5. **Tester le flow auth bout-en-bout** une fois les credentials Google configurés en prod : login → callback → cookie session → `/api/v1/auth/me`. Test manuel requis.

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

Pour qu'un agent (Claude Code, Aider, opencode, etc.) reprenne efficacement :

1. **Travail autonome multi-sessions** : commencer par [`agent/README.md`](./agent/README.md). Le dossier `agent/` contient le protocole complet (permissions, git workflow, pitfalls, skills) + une mémoire condensée dans [`agent/memory/PROJECT_SNAPSHOT.md`](./agent/memory/PROJECT_SNAPSHOT.md).
2. **Plan de complétion MVP** : [`.docs/10-mvp-completion-plan.md`](./.docs/10-mvp-completion-plan.md) — jalons M1 (OAuth), M2 (auth guard + extracteur), M3 (durcissement).
3. **Travail ponctuel (une session)** : lire dans l'ordre `README.md` → `STATE.md` (ce fichier) → `DECISIONS.md` → `.docs/01-product-spec.md` → `.docs/02-tech-architecture.md`.
4. **Vérifier l'état actuel** :
   - `git log --oneline -10`
   - `wsl gh run list --branch main --limit 3`
   - `curl https://filum-production-07bb.up.railway.app/health`
5. **Choisir une tâche** : suivre le jalon courant du plan MVP, sinon prendre dans « Prochaines étapes » ci-dessus.
6. **Travailler** : branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite (cf. [`agent/GIT_WORKFLOW.md`](./agent/GIT_WORKFLOW.md)).
