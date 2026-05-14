# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-14 (PR #34)** — **Diagnostic & filet de sécurité publish** : le user a signalé que le bug `Failed to fetch` persistait après PR #33 mergée. Triple action : (1) endpoint `publish_card` enveloppé d'un `try/except` qui garantit une réponse JSON 500 propre quelle que soit l'exception (au lieu d'une connexion qui meurt en silence) ; (2) `/health` retourne désormais `commit` (SHA git Railway) pour vérifier en un `curl` que Railway a bien redéployé ; (3) message d'erreur frontend publish reformulé pour guider le user vers la console DevTools. Voir CHANGELOG `[Unreleased]`.

**2026-05-14 (PR #33)** — Fix critique du publish : `MissingGreenlet` sur `card.user.username` post-commit/refresh dans `CardService.publish_card`. Navigateur recevait `TypeError: Failed to fetch` (pas un bug réseau ni CORS, mais la sérialisation HTTP qui mourait sans body). PITFALLS §1.4 enrichi avec le symptôme côté frontend.

**2026-05-14 (PR #32)** — **Pivot crypto** : signature désormais sur le lien créateur·ice ↔ contenu via triplet `(creator_id, content_url, attested_at)`, plus sur la fiche. Reformulation copy globale, suppression FAQ sécurité, ajout Filum Desktop dans roadmap. Voir ADR-019 dans `DECISIONS.md`. La PR backend de bascule (migration `006_remove_card_signature`, table `content_attestations`, refonte endpoint publish) reste à ouvrir.

**2026-05-13** — Session PR #31 : MVP améliorations — CI lint frontend fixée (`.prettierignore` + format 4 fichiers), README mis à jour. Voir `CHANGELOG.md` pour le détail.

### PR #30 — Missing Request type hints (mergée)
- **Root cause du bug "An error occurred"** : `get_current_user` dans `sources.py` et `users.py` avait `request` sans `: Request` type hint → FastAPI traitait `request` comme paramètre query au lieu d'injecter l'objet Request → tous les endpoints sources retournaient 422.
- Fichiers : `sources.py:63`, `users.py:20` — ajout de `request: Request` + import `Request` dans `users.py`.

### PR #31 — MVP améliorations (cette session)
- **3 nouvelles pages** : `/features` (fonctionnalités dispo + à venir), `/roadmap` (feuille de route), `/security` (cryptographie, clés, FAQ)
- **OpenGraph dynamique** : backend `GET /api/v1/og?title=&creator=` génère une image PNG 1200×630 via Pillow + police DejaVu Serif ; frontend `og:image` / `twitter:image` sur les fiches publiques
- **Logout fix** : `invalidateAll()` après déconnexion pour rafraîchir `data.user` — l'avatar Google ne reste plus affiché
- **Publish** : message "Impossible de contacter le serveur" au lieu de "Failed to fetch" en cas d'erreur réseau
- **Texte "Pour qui?"** : 4e catégorie "Créateur·ice·s de contenu" + note "N'oubliez pas de citer..." sur accueil et À propos
- **About enrichi** : histoire, valeurs (transparence, pérennité, liberté), liens vers /security et GitHub

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
|---|---|---|
| `main` | Branche de déploiement. `feat/iteration-3-dashboard-ci`, `feat/iteration-3-extractor-wayback`, `fix/source-excerpts-missinggreenlet` (PR #30) mergées et supprimées. `feat/mvp-mk2` (PR #31) en cours — CI lint frontend fixée, prête pour merge. |

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
- Sécurité : dépendance `Pillow` ajoutée (OG images dynamiques, installée via `uv add Pillow`)

---

## Stack effective déployée

### Backend
- Python 3.12 + FastAPI async + SQLAlchemy 2.x async + Alembic
- PostgreSQL (Railway plugin, lié via `${{Postgres.DATABASE_URL}}`)
- Crypto : Ed25519 + AES-GCM + HS256 (PyJWT, plus de python-jose, cf. ADR-014)
- Models : User, BiblioCard, Source, AuditEvent
- API REST sous `/api/v1/` : auth, cards, sources, users, og
- Migrations Alembic exécutées au boot dans le `CMD` Docker
- 72 tests (pytest — unit + integration)
- Extracteur URL : `app/extractors/url_extractor.py` (Crossref + HTML scraping)
- Endpoint `GET /api/v1/sources/extract` (no auth, best-effort metadata)
- Générateur OpenGraph : `app/services/og_image.py` (Pillow, police DejaVu Serif), endpoint `GET /api/v1/og?title=&creator=`

### Frontend
- SvelteKit 2 + Svelte 5 + TypeScript + Tailwind, déployé sur Vercel
- pnpm 10.33.4 pinned via `packageManager` (cf. ADR-013)
- Design system : Button, Input, Card, Avatar, Badge, Alert, SourceTypeBadge, SourceGraph, SourceDetailPanel
- Stores : auth, cards
- Routes : home, dashboard, features, roadmap, security, about, public card (avec graphe D3, OpenGraph dynamique, SSR + JSON-LD), user profile, `/dashboard/new` (création fiche 2 étapes)
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
| Signature fiche encore présente en base (post-ADR-019) | Moyenne | `BiblioCard.canonical_hash/signature/signed_at` à dropter dans migration `006`. Table `content_attestations` à créer. Frontend déjà désaligné (n'affiche plus). |
| Bug publish « Impossible de contacter le serveur » | À reproduire | `POST /cards/{id}/publish` lève `TypeError: Failed to fetch` côté navigateur. Possibles causes : CORS, cookie cross-site, ou bug backend non-JSON. À reproduire via DevTools. |
| `impact_factor` toujours `null` | Faible | OpenAlex supprimé (dead code), pas de fallback |
| ~~Publish renvoie « Impossible de contacter le serveur »~~ | **Résolu PR #33** | `MissingGreenlet` sur `card.user.username` post-commit/refresh dans `CardService.publish_card`. La sérialisation HTTP mourait sans body, le navigateur recevait `TypeError: Failed to fetch`. Fix : capture des scalaires avant `commit`, suppression du `refresh` superflu. PITFALLS §1.4 enrichi. |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5 |
| ~~Cookie `samesite=lax`~~ | **Résolu** | Bascule `samesite=none + secure=True` conditionnée sur `settings.debug` (PR jalon M1) |
| Pas de domaine custom | Feature | Brancher `filum.app` quand prêt |

---

## État production vérifié (2026-05-13)

Vérifié par `curl` sur les URL prod, pas par lecture des docs :

- ✅ Backend `/health` → 200 OK, version 0.1.0
- ✅ API `/api/v1/@example/memoire-et-cerveau` → 200, 16 sources (dont 2 non-académiques), signature Ed25519 présente
- ✅ Migration 004 **appliquée** : les nouveaux champs (`citations_count`, `subscribers_count`, `views_count`, `impact_factor`, `conflict_of_interest`, `excerpts[]`) sont bien sérialisés dans la réponse API
- ✅ Frontend SSR fonctionne : `<script type="application/ld+json">` présent dans le HTML statique, meta `og:title`/`og:description`/`og:image` présents
- ✅ OpenGraph dynamique : `GET /api/v1/og?title=Test` retourne une image PNG 1200×630
- ✅ Nouvelles pages : `/features`, `/roadmap`, `/security` accessibles sur le frontend
- ✅ **Seed P0 résolu** : `_get_or_create_demo_card` ne fait plus early-return. Les sources sont delete+recreate à chaque run, les nouveaux champs (excerpts, conflits, indicateurs) sont rafraîchis, et 2 nouvelles sources non-académiques sont ajoutées (documentaire NOVA + dessin Cajal). La fiche démo prod est re-signée à chaque run du seed.

---

## Prochaines étapes par priorité (basé sur l'état prod vérifié)

### P0 — 🚀 Session PR #31 — Nouveau contenu et OpenGraph

Nouvelles pages (Features, Roadmap, Security), OpenGraph dynamique fonctionnel, logout fixé, "Pour qui?" enrichi. CI lint frontend fixée (`.prettierignore` + format 4 fichiers). Prête pour merge de `feat/mvp-mk2` vers `main`.

### P1 — Vision produit

- Améliorer l'extraction de métadonnées (plus de sources supportées, fallbacks)
- Tester le flow auth end-to-end avec un vrai utilisateur
- Finaliser l'intégration du copier-coller de bibliographie (auto-fill des sources)

### P2 — Qualité interne (dette dormante)

- Réécrire test composant Svelte 5 (compatible testing-library Svelte 5)
- Nettoyage `authority_level` (legacy, plus utilisé par l'UI)
- Réduire cold start Railway (keep-alive ou instance hobby)

### P3 — Ouverture produit

- Import Zotero / BibTeX / Obsidian
- Export PDF / CSV / Excel / JSON / BibTeX
- Plugin navigateur (ajout de source en un clic)
- API publique + serveur MCP
- Domaine custom `filum.app`
- Score de sourçage IA

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
