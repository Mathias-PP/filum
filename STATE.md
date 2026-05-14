# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-05-15 — Décisions structurantes capturées (ADR-021 + ADR-022), aucune exécution.**

Crédits Railway sont passés à $0 le 2026-05-14 puis revenus à $4.86 (28 jours restants) le 2026-05-15 — probablement re-crédit mensuel automatique du Hobby Plan, à confirmer côté billing dashboard. Migration mise en pause, **mais les choix sont gelés** dans `DECISIONS.md` pour pouvoir basculer rapidement quand le besoin se représente :

- **ADR-021** : projet à renommer **Filum → Philum** (référence aux phylums biologiques et arbres phylogénétiques, en plus du fait que `filum.com/.fr/.app` sont tous squattés à 300-3000 €). Domaines libres : `philum.fr` (5,10 € la 1re année) et `philum.app` (~12 €/an défensif).
- **ADR-022** : cible de migration figée = **Infomaniak Public Cloud** (datacenter Genève D3, OpenStack, 300 € de crédits offerts sur 3 mois, ~5-8 €/mois pour la taille de Philum après les crédits, soit ~85-130 €/an avec domaines).

Voir les deux ADR pour le détail architecture, étapes, coûts.

**Action prochaine** : surveiller le billing Railway — si CB requise pour continuer après les 28 jours, exécuter la PR de migration (rename + déploiement Infomaniak) en suivant le plan ADR-022.

---

## Mises à jour précédentes

**2026-05-14 (PR taxonomie en cours)** — **Refonte taxonomie sources en 3 axes orthogonaux + corrections hero + parent links UI (ADR-020).**

- **Taxonomie 3 axes** : `source_type` (mélangeait format + catégorie) et `authority_level` (legacy) supprimés. Remplacés par `format` (5 valeurs), `category` (12), `author_kind` (9). Migration Alembic 007 avec backfill best-effort.
- **Graphe coloré par `author_kind`** : la couleur du nœud encode désormais l'origine épistémique (chercheur / média / institution-publique / etc.), pas un mélange format/catégorie. Palette dans `apps/frontend/src/lib/utils/author-colors.ts`.
- **Formulaire d'ajout de source** : 1 dropdown → 3 dropdowns obligatoires + dropdown optionnel « Cette source en cite une autre déjà ajoutée ? » qui persiste `parent_source_id`. Composants `AuthorKindBadge`, `FormatBadge`, `CategoryBadge` côté détail.
- **Bug fix** : `POST /cards/{id}/sources` ignorait silencieusement `parent_source_id` au CREATE (champ jamais passé au constructeur `Source(...)`). Le seed le contournait par insertion directe.
- **Garde levée** : `POST/PATCH/DELETE /sources/...` n'interdisent plus l'édition sur fiches publiées (cohérent avec ADR-019 — fiches mutables).
- **Hero accueil** : suppression du mot « contenu » dans « chaque contenu original que vous revendiquez » (collision sémantique avec l'ex-`source_type=original`) et refonte du SVG (lignes droites, 2 arêtes pointillées entre sources pour illustrer le feature parent, labels mis à jour avec la nouvelle taxonomie).
- `CardStats` re-keyé : `peer_reviewed`/`institutional`/... → `chercheur`/`media`/`institution_publique`/`individu`. La fiche publique adapte les 2 tuiles statistiques.
- Branche `feat/taxonomy-redesign`, PR à ouvrir, merge manuel par l'utilisateur.

**2026-05-14 (PR #43 mergée)** — **Passe UX/UI : mobile nav + dashboard édition + hero + 404.**

- **Mobile nav** : menu hamburger ajouté dans `+layout.svelte`. Les 4 onglets de navigation (`Fonctionnalités`, `Roadmap`, `Sécurité`, `À propos`) étaient inaccessibles sur mobile (`hidden md:flex` sans alternative). Drawer fermé sur Escape ou clic extérieur.
- **Dashboard fiches publiées** : ajout des boutons Voir / Éditer / Supprimer (les fiches sont mutables depuis ADR-019, l'édition réutilise `/dashboard/new/{id}/sources`).
- **Compteurs dashboard** (X brouillons, Y publiées) + skeleton loader.
- **Hero accueil refondu** : layout 2 colonnes, illustration SVG vectorielle dédiée (graphe de citation stylisé avec types de sources colorés et nœud central animé), background dégradé subtil.
- **Page 404 custom** (`+error.svelte`) avec CTA contextuels.
- **`/privacy`** : stub minimal pour éviter le 404 footer.
- **Loading states** : labels dynamiques + `disabled` pendant submit sur création fiche, ajout source, publication.
- Branche `feat/ux-mobile-dashboard-hero`, PR à ouvrir, merge manuel par l'utilisateur.

**2026-05-14 (post-PR #40)** — **Axe C terminé et déployé en prod.** Migration 006 + table `content_attestations` + endpoints attestation + seed signing sont opérationnels. Plusieurs crashs résolus. Plan 3 axes révisé : le P0 (Axe C) est livré, place au P1 (Axe B — archivage multi-cible).

**2026-05-14 (PR #39 + PR #40) — Axe C déployé, 2 crashs production résolus.**

- **PR #39** — Fix migration 006 : `op.drop_index("ix_biblio_cards_canonical")` retiré car l'index n'a jamais été créé en base (seul `ix_biblio_cards_canonical_hash` auto-généré par `Column(index=True)` existe). PostgreSQL cascade-drop automatiquement l'index avec la colonne. Conflits de merge résolus (rebased on `main` après merge PR #38). CI toute verte.
- **PR #40** — Fix `NotNullViolationError` sur `content_attestations.created_at` : le modèle avait `default=None, server_default=None`, ce qui forçait SQLAlchemy à envoyer `NULL` dans l'INSERT, court-circuitant le `server_default=sa.func.now()` défini dans la migration 006. Fix : `server_default=func.now()` sans `default=None`.
- Root cause documentée dans [`agent/PITFALLS.md`](agent/PITFALLS.md) §1.8.
- Backend stable : migration 006 s'exécute correctement, seed demo crée les attestations, endpoints attestation fonctionnels.

**2026-05-14 (PR #36) — VRAIE root cause du bug publish trouvée et corrigée.** Après 3 PRs de fausses pistes (#33 MissingGreenlet, #34 try/except + diagnostic, #35 endpoint /health/publish-diagnose), l'endpoint diagnostic a exposé le vrai traceback : `asyncpg.DataError: can't subtract offset-naive and offset-aware datetimes`. `CardService.publish_card` faisait `datetime.now(UTC)` sans `.replace(tzinfo=None)` (oubli du pattern PITFALLS §1.5) → colonne `TIMESTAMP WITHOUT TIME ZONE` refusait → commit aborté → `get_db` cleanup retentait le commit sur session morte → réponse interrompue mid-stream → CORS header jamais ajouté → user voit "blocked by CORS policy" alors que CORS marche partout ailleurs. Fix : `.replace(tzinfo=None)` + rollback défensif dans le try/except du endpoint. PITFALLS §1.5 enrichi.

**2026-05-14 (PR #34)** — Diagnostic & filet de sécurité publish : le user a signalé que le bug `Failed to fetch` persistait après PR #33 mergée. Triple action : (1) endpoint `publish_card` enveloppé d'un `try/except` qui garantit une réponse JSON 500 propre quelle que soit l'exception (au lieu d'une connexion qui meurt en silence) ; (2) `/health` retourne désormais `commit` (SHA git Railway) pour vérifier en un `curl` que Railway a bien redéployé ; (3) message d'erreur frontend publish reformulé pour guider le user vers la console DevTools. Voir CHANGELOG `[Unreleased]`.

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

**Phase 1 — MVP complet + Axe C (ADR-019) livré.** Tous les jalons M1+M2+M3 sont terminés. Axe C (refonte backend post-ADR-019) également déployé : migration 006, table `content_attestations`, endpoints attestation, désormais la signature porte sur le triplet `(creator_id, content_url, attested_at)` et non plus sur la fiche. Le flow complet login → création → signature → attestation → publication est opérationnel.

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
| `main` | Branche de déploiement. PR #39 (fix migration 006 drop index) et PR #40 (fix model `created_at` NULL) mergées et supprimées. Axe C fully live. |

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
| ~~Signature fiche encore présente en base (post-ADR-019)~~ | **Résolu** | Migration 006 mergée et déployée : table `content_attestations` créée, colonnes `canonical_hash/signature/signed_at` dropées de `biblio_cards`. Seed demo crée les attestations. |
| `impact_factor` toujours `null` | Faible | OpenAlex supprimé (dead code), pas de fallback |
| ~~Publish renvoie « Impossible de contacter le serveur »~~ | **Vraie résolution PR #36** | `asyncpg.DataError` sur `card.signed_at = datetime.now(UTC)` (manquait `.replace(tzinfo=None)`) dans `CardService.publish_card`. Commit aborté → `get_db` cleanup retente sur session morte → réponse interrompue → CORS header jamais ajouté → user voyait "blocked by CORS policy". Fix : naive UTC datetime + rollback défensif. PITFALLS §1.5 enrichi. PR #33 (MissingGreenlet) et #34 (try/except) n'étaient pas la vraie cause mais restent utiles comme filet de sécurité. |
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

> Plan détaillé dans [`.docs/12-next-steps.md`](.docs/12-next-steps.md). Cette section est l'**index** opérationnel.

### P0 — Axe C : refonte backend post-ADR-019 ✅ **LIVRÉ**

Migration 006 mergée et déployée. Table `content_attestations` en prod. Endpoints attestation fonctionnels. Seed demo signé. Deux bugs résolus en cours de route (DROP INDEX inexistant, `created_at` NULL).

### P1 — Axe B : archivage multi-cible (1 semaine)

- Refacto `WaybackService` → `ArchiveOrchestrator` (Wayback → Archive.today → Playwright)
- Table `archive_attempts` + retry exponentiel via cron Railway
- Badge archive sur chaque source côté UI
- Endpoint public `GET /sources/{id}/archive`

### P2 — Validation produit (1 semaine)

Interviewer 3 créateurs cibles avant Axe A : « voudriez-vous héberger vos vidéos/articles directement sur Filum, ou Filum doit-il rester un index ? »
Sans validation, ne pas attaquer Axe A.

### P3 — Axe A : stockage cloud R2 (2-3 semaines, conditionnel)

- ADR-020 : Cloudflare R2 comme blob store principal (10 GB free + zero egress), Internet Archive en miroir long terme
- Service `BlobStorage` (interface) + impls R2 + InternetArchive
- Migration `007_add_content_files`
- Endpoints `POST /uploads/initiate` (URL pré-signée R2) + `/uploads/complete`
- Frontend `<ContentUploader>` avec upload direct R2
- Sécurité : ClamAV scan, max 500 Mo/fichier, vérif checksum SHA-256

### P4 — Autres (mûr mais non bloquant)

- Tests E2E Playwright (golden path)
- Import Zotero / BibTeX / Obsidian (bloqué jusqu'à axe C livré)
- Plugin navigateur (après 3-5 créateurs actifs)
- Domaine custom `filum.app` (après premier ambassadeur prêt)
- Améliorer l'extraction de métadonnées (fallbacks supplémentaires)

### P2 — Qualité interne (dette dormante)

- Réécrire test composant Svelte 5 (compatible testing-library Svelte 5)
- ~~Nettoyage `authority_level` (legacy, plus utilisé par l'UI)~~ **Résolu par ADR-020** : colonne droppée par migration 007
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
