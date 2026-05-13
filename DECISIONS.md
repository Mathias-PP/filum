# Journal des décisions

> Ce fichier consigne les décisions techniques et stratégiques importantes prises au fil du projet. Format inspiré des « Architecture Decision Records » (ADR).
>
> **Une entrée par décision.** Chaque entrée est datée, contient le contexte, l'option retenue, les alternatives écartées, et les conséquences.

---

## ADR-001 — Stack backend : FastAPI + PostgreSQL + DuckDB + dbt

**Date** : 2026-04 (phase de planification)

**Contexte**
Le projet doit servir à la fois de produit pour les créateurs et de pièce maîtresse dans un portfolio Data Engineer. Le développement initial se fait en solo avec assistance IA, sur 1 semaine pour un prototype démontrable.

**Options envisagées**
- Next.js full-stack (rejetée : peu différenciant pour un profil Data Engineer, lourdeur du doublement HTML+JSON)
- Rust pour le backend (rejetée : courbe d'apprentissage incompatible avec 1 semaine MVP, pas un signal Data Engineer fort)
- FastAPI + PostgreSQL + DuckDB + dbt (retenue)

**Justifications**
- Python + FastAPI : maîtrise par les LLMs maximale (efficacité du dev assisté IA), écosystème data dense
- PostgreSQL pour le transactionnel : standard, fiable
- DuckDB pour les analytics : moderne, valorisant pour le portfolio, parfait pour les requêtes sur le graphe de citations
- dbt-core sur DuckDB : signal Data Engineer fort, transformations versionnées et testées

**Conséquences**
- Bon TTM (time to market)
- Stack moderne et valorisable
- Pas de Rust en phase 1 — éventuelle migration de modules critiques en phase 3 (c2pa-rs notamment)

---

## ADR-002 — Frontend : SvelteKit en TypeScript

**Date** : 2026-04

**Contexte**
Le front doit être performant, beau, et rapide à développer. Pas de surcouche framework UI lourde.

**Options envisagées**
- Next.js (rejetée : lourdeur, duplication HTML+JSON, peu différenciant)
- SvelteKit (retenue)
- Astro avec îlots React (envisagée : très performante mais moins de cohérence pour une SPA-like)

**Justifications**
- SvelteKit : syntaxe ultra-claire, bundle léger, excellent rendu serveur
- Compatible avec un déploiement Vercel/Netlify gratuit
- Maîtrisé par les LLMs

**Conséquences**
- Apprentissage léger nécessaire si non maîtrisé
- Pas de duplication HTML+JSON contrairement à Next.js

---

## ADR-003 — Cryptographie en MVP : Ed25519 réel, sans intégration C2PA

**Date** : 2026-04

**Contexte**
Décider du niveau d'investissement crypto pour la semaine 1.

**Options envisagées**
- Tout simulé (rejetée : creux)
- Hash SHA-256 réel + signature Ed25519 réelle, sans C2PA (retenue)
- Intégration complète c2pa-rs (rejetée pour la phase MVP, prévue pour la phase 3)

**Justifications**
- Hash et signature réels sont peu coûteux à implémenter (`cryptography` Python)
- Format C2PA peut être adopté plus tard sans refactoring majeur (signatures Ed25519 réutilisables)

**Conséquences**
- MVP techniquement sérieux dès le départ
- Migration C2PA prévue en phase 3 sans refonte du modèle de données

---

## ADR-004 — OAuth en MVP : Google uniquement

**Date** : 2026-04

**Contexte**
Décider du provider d'identité pour le MVP.

**Options envisagées**
- Pas d'OAuth (rejetée : creux)
- GitHub OAuth seul (envisagée)
- Google OAuth seul (retenue)
- Multi-provider (rejetée pour MVP : trop de setup)

**Justifications**
- Google couvre la quasi-totalité des créateurs cible (un compte Google est universel)
- Setup ~2-3h vs jours pour OAuth multi-provider
- Extension prévue à YouTube en phase 2 (qui passe par Google OAuth)

**Conséquences**
- Setup OAuth Google nécessaire dès la phase MVP
- Architecture d'identité prévue pour accueillir d'autres providers en phase 2

---

## ADR-005 — Snapshots de sources : API Wayback Machine

**Date** : 2026-04

**Contexte**
Décider du mécanisme d'archivage des URLs sources.

**Options envisagées**
- Pas de snapshots (rejetée : creux)
- API Wayback Machine d'Internet Archive (retenue)
- Snapshots propres via Puppeteer/Playwright (rejetée pour MVP : complexité)

**Justifications**
- Wayback Machine : gratuit, fiable, mondialement reconnu
- L'API `https://web.archive.org/save/<url>` est simple à intégrer
- Pas de stockage côté Filum nécessaire en phase 1

**Conséquences**
- Dépendance externe à Internet Archive en phase 1 — acceptable
- Investigation pour snapshots propres en phase 2-3 si volumétrie ou besoins de contrôle

---

## ADR-006 — Saisie des sources : commencer par formulaire manuel

**Date** : 2026-04

**Contexte**
Le créateur entre ses sources dans la fiche. Trois flux possibles : manuel, extraction IA depuis texte, import standard (Zotero/BibTeX/RIS).

**Options envisagées**
- Formulaire manuel uniquement (retenue pour MVP semaine 1)
- Extraction IA depuis du texte collé (prévue pour phase 2)
- Import Zotero/BibTeX/RIS (prévu pour phase 3)

**Justifications**
- Formulaire manuel : aucun risque, base solide
- L'extraction IA et l'import standardisé sont des accélérateurs de saisie ajoutés ensuite

**Conséquences**
- Friction utilisateur initiale plus élevée
- Architecture API conçue pour accepter plusieurs flux d'entrée dès le départ (un endpoint qui accepte une liste structurée de sources, quelque soit la source amont)

---

## ADR-007 — Déploiement MVP : Railway + Vercel/Netlify

**Date** : 2026-04

**Contexte**
Le MVP doit être déployable rapidement et gratuitement.

**Options envisagées**
- Vercel full-stack (rejetée car backend Python pas idéal sur Vercel Serverless)
- Railway pour le backend + Vercel/Netlify pour le frontend (retenue)
- Scaleway dès le MVP (rejetée : surcoût d'apprentissage Docker)
- Fly.io ou Render (envisagées : alternatives valables à Railway)

**Justifications**
- Railway : tier gratuit suffisant pour MVP, Postgres inclus, déploiement en 5 min
- Vercel ou Netlify pour SvelteKit : déploiement instantané, CDN
- Scaleway prévu pour phase 3 (production souveraine européenne)

**Conséquences**
- Migration vers Scaleway prévue dès que l'audience justifie le narratif souverain
- Infrastructure totalement gratuite en phase MVP

---

## ADR-008 — Nom du projet : Filum (provisoire)

**Date** : 2026-04

**Contexte**
Choisir un nom de code pour le projet.

**Options envisagées** : Filum, Stemma, Colophon, Upstream, Tracé, Provenance

**Retenue** : Filum, comme nom de code de travail

**Justifications**
- Court, latin, évoque la filiation et le fil généalogique
- Distinctif (pas de doublons en tech ou en crypto)
- Portable linguistiquement
- Décision révisable avant le lancement public

**Conséquences**
- Domaines à réserver (`filum.app`, `filum.org`, `filum.eu`, `filum.io`)
- Décision définitive à prendre avant le lancement public (phase 2)

---

## ADR-009 — Chiffrement AES-GCM au lieu de Fernet

**Date** : 2026-05

**Contexte**
Chiffrement de la clé privée Ed25519 de chaque utilisateur avant stockage en base.

**Options envisagées**
- Fernet (standard dans la communauté Python, simple) — rejeté car obsolète
- AES-GCM avec `cryptography` (retenue)

**Justifications**
- AES-GCM est le standard moderne, authentifié (AEAD), recommandé par les autorités (ANSSI, NIST)
- `cryptography` est déjà une dépendance du projet pour Ed25519
- Fernet est une surcouche qui masque les détails cryptographiques (pédagogiquement moins intéressant pour un portfolio Data Engineer)

**Conséquences**
- Implémentation légèrement plus verbeuse que Fernet
- Code crypto plus transparent et valorisable

---

## ADR-010 — `case_sensitive=True` dans pydantic-settings : variables d'env en lowercase

**Date** : 2026-05

**Contexte**
La classe `Settings` utilise `case_sensitive=True` dans `SettingsConfigDict`. Cela casse la lecture des variables d'environnement en SCREAMING_SNAKE_CASE.

**Options envisagées**
- Passer `case_sensitive=False` (rejeté : moins de contrôle sur les collisions de noms)
- Conserver `case_sensitive=True` et utiliser des noms lowercase dans les env vars partout (retenue)

**Justifications**
- Cohérence avec la définition exacte des champs dans la classe Settings
- `case_sensitive=True` évite les ambiguïtés (ex: `database_url` vs `DATABASE_URL`)
- GitHub Actions gère correctement les env vars lowercase

**Conséquences**
- `.env` : utiliser `database_url`, `session_secret`, etc. (pas `DATABASE_URL`)
- CI/CD : env vars en lowercase dans `ci.yml` et `cd.yml`
- Conftest de test : env vars en lowercase avant import des modules app

---

## ADR-011 — pnpm 11 : workaround `ERR_PNPM_IGNORED_BUILDS`

**Date** : 2026-05

**Contexte**
pnpm 11 a introduit une politique stricte sur les build scripts (`onlyBuiltDependencies`). esbuild (dépendance transitive de SvelteKit/Vite) n'est pas autorisé à exécuter ses postinstall scripts, causant `ERR_PNPM_IGNORED_BUILDS` avec exit code 1.

**Options envisagées**
- `onlyBuiltDependencies` dans `package.json` (essayé, ignoré par pnpm 11 en CI)
- `.pnpm-approve-builds.json` (essayé, ignoré par pnpm 11)
- `pnpm config set onlyBuiltDependencies` + `|| true` sur install (retenue)

**Justifications**
- La config dans `package.json` est respectée par pnpm local mais pas systématiquement en CI
- `.pnpm-approve-builds.json` est déprécié par pnpm 11
- `|| true` est un workaround pragmatique : l'install réussit malgré le warning, l'erreur exit code est supprimée

**Conséquences**
- Toute job CI frontend avec `pnpm install` doit avoir `|| true`
- La config `pnpm config set onlyBuiltDependencies` reste présente comme bonne pratique
- À réévaluer quand pnpm 11 sera plus mature ou que le bug sera fixé

---

## ADR-012 — Tests DB async : SQLite + aiosqlite, import explicite des modèles

**Date** : 2026-05

**Contexte**
Tests unitaires des services qui dépendent de la base de données (AuthService). Nécessité d'une isolation par test et de la création/destruction des tables.

**Options envisagées**
- PostgreSQL de test via Docker (rejeté : complexité, CI déjà configurée en SQLite)
- SQLite + aiosqlite avec fixture `db_session` créant les tables par test (retenue)

**Justifications**
- SQLite est utilisée en CI (ci.yml : `database_url: sqlite+aiosqlite:///./test.db`)
- Pas de dépendance Docker pour les tests unitaires
- aiosqlite compatible avec SQLAlchemy async

**Piège évité**
`Base.metadata.create_all` ne crée rien si les modèles ne sont pas importés. En conftest, il faut importer explicitement `app.models.user`, `app.models.biblio_card`, etc. avant d'appeler `create_all`, car SQLAlchemy ne découvre les tables qu'au moment de l'import de chaque modèle.

**Conséquences**
- `conftest.py` importe tous les modèles avant `create_all`
- Tables créées et détruites à chaque test (via `db_session` fixture)
- Performances acceptables (38 tests en ~11s)

---

## ADR-013 — Pin pnpm 10 via `packageManager` + suppression des workarounds CI

**Date** : 2026-05

**Contexte**
Le job `build-frontend` échouait sur `pnpm run build`. Investigation :

1. **Cause racine pnpm 11** : `pnpm install` retourne exit 1 sur `ERR_PNPM_IGNORED_BUILDS` (esbuild postinstall script non approuvé), **même si toute la résolution + l'écriture sur disque ont réussi** (les binaires esbuild proviennent de sous-packages prebuilds, le postinstall était cosmétique). pnpm 11 réexécute en plus un `pnpm install` interne avant chaque `pnpm run <script>` (`verify-deps-before-run=true` par défaut), reproduisant l'exit 1 fatalement.
2. **Aggravation** : pnpm 11 réécrit `pnpm-workspace.yaml` à chaque install pour y insérer un bloc placeholder malformé `allowBuilds: esbuild: set this to true or false`, qui empoisonne la suite du fichier et invalide le `onlyBuiltDependencies` qu'on essaye d'y mettre.
3. **Cause racine secondaire** : `svelte.config.js` portait `kit.vitePlugin.inspector`, option supprimée dans SvelteKit 2 (`Unexpected option config.kit.vitePlugin`) — invisible tant que (1) bloquait avant.

**Options envisagées**
- Empiler des workarounds pnpm 11 : `|| true` sur install + `pnpm exec` + `verify-deps-before-run=false` (rejetée : 3 workarounds pour 1 bug, masque la cause)
- Migrer vers npm ou yarn (rejetée : coût de migration disproportionné)
- **Pin pnpm 10 via `packageManager: "pnpm@10.33.4"` dans `package.json`** (retenue)

**Justifications**
- pnpm 10 n'a pas le comportement strict-exit-1 ni le re-install implicite — l'ancien comportement est ce que tout l'écosystème SvelteKit assume aujourd'hui
- `pnpm/action-setup@v4` honore automatiquement le champ `packageManager` → CI alignée avec local et avec le Dockerfile (qui utilise déjà `corepack enable pnpm`)
- Permet `--frozen-lockfile` en CI (builds déterministes)
- Aucun fichier supplémentaire (pnpm-workspace.yaml, .pnpm-approve-builds.json) — restaure `pnpm.onlyBuiltDependencies` dans `package.json` (format pnpm 10 standard)

**Conséquences**
- `pnpm install` exit 0, `pnpm run build` direct, CI lisible
- Mêmes versions de pnpm partout : CI, local, Docker
- `.pnpm-approve-builds.json` supprimé (artefact pnpm 11 non lu par pnpm 10)
- `pnpm-workspace.yaml` supprimé (réécrit par pnpm 11 avec du junk, inutile pour ce projet mono-package)
- Bloc `kit.vitePlugin.inspector` retiré de `svelte.config.js`
- Suppression dans CI : `|| true` sur install, `pnpm exec vite build`, `pnpm config set verify-deps-before-run false`, `continue-on-error: true` sur Type Check
- `lint-frontend` et `test-frontend` gardent leur `|| true` : ils ont des bugs réels (deps eslint manquantes, incompat Svelte 5 + testing-library) à traiter dans une PR séparée (cf. STATE.md follow-ups)
- À surveiller : si SvelteKit pousse pnpm 11+ exigé, on remontera le pin

**Reproductibilité**
```bash
cd apps/frontend
pnpm install --frozen-lockfile     # exit 0
pnpm run build                     # ✓ built in ~10s
```

---

## ADR-014 — Migration `python-jose` → `PyJWT`

**Date** : 2026-05

**Contexte**
`actions/dependency-review-action@v4` (PR check GitHub) bloque le merge sur `ecdsa@0.19.2 — Minerva timing attack on P-256 (HIGH)`. `ecdsa` est tiré comme transitive dep par `python-jose`. Filum n'utilise PAS ECDSA (HS256 = HMAC symétrique pour JWT, Ed25519 via `cryptography` pour signatures de fiches) → CVE non exploitable, mais bloquant côté process.

**Options envisagées**
- Allowlist le CVE (rejetée : la lib `python-jose` est aussi peu maintenue ; on stocke une dette sans valeur)
- Migrer vers `authlib` (rejetée : surdimensionné, on n'utilise que encode/decode)
- **Migrer vers `PyJWT`** (retenue : standard de fait, API identique à jose, mainteneurs actifs)

**Justifications**
- API identique : `jwt.encode(payload, secret, algorithm='HS256')` et `jwt.decode(token, secret, algorithms=['HS256'])` — 0 changement de logique
- Exception hierarchy plus propre : `jwt.InvalidTokenError` est parent de `ExpiredSignatureError`, `InvalidSignatureError`, `DecodeError` → couvre les 3 cas testés en une seule clause
- Pas de transitive deps cryptographiques inutiles (ecdsa, pyasn1, rsa supprimés)
- Type hints natifs : suppression d'un `# type: ignore` dans `auth.py`

**Conséquences**
- 4 fichiers modifiés : `pyproject.toml`, `uv.lock`, `app/services/auth.py`, `tests/unit/test_auth.py`
- `uv.lock` : -65 lignes (suppression de ecdsa, pyasn1, rsa)
- mypy + ruff propres
- Dependency Review CI passe (plus de CVE haute sévérité)
- Aucun changement de comportement runtime

---

## ADR-015 — Déploiement Railway via intégration GitHub native (pas de workflow CD)

**Date** : 2026-05

**Contexte**
Le workflow `cd.yml` initial ne fonctionnait pas :
- YAML invalide : `workflow_dispatch:` était au top-level au lieu d'être nesté sous `on:` → la CI rejetait le fichier au parsing (0 jobs, 0s runtime)
- `railway-devrel/railway-actions@v1` n'existe pas sur le marketplace GitHub (fiction d'un LLM lors du scaffolding initial)
- Variables d'env passées en UPPERCASE (`DATABASE_URL`, etc.) contradictoire avec ADR-010 → silent fallback aux defaults
- Scope démesuré pour un MVP : staging + production avec 10 secrets distincts

**Options envisagées**
- Réécrire `cd.yml` from scratch avec le CLI Railway (`@railway/cli`) ou `bervProject/railway-app` (rejetée : duplique ce que Railway fait nativement)
- Utiliser GitHub Actions pour build une image Docker puis Railway pour la pull (rejetée : 2 sources de vérité, latence)
- **Intégration GitHub native de Railway** (retenue) : Railway watch le repo, build et deploy automatiquement à chaque push sur main

**Configuration Railway adoptée**
- Service backend lié à `Mathias-PP/filum`, branch `main`
- **Root Directory** : `apps/backend`
- **Builder** : Dockerfile (auto-détection `apps/backend/Dockerfile`)
- **Wait for CI** : enabled — Railway attend que GitHub Actions soit vert avant de déployer
- **Healthcheck Path** : `/health`
- **Port** : injecté via `$PORT` dans le `CMD` Docker (`${PORT:-8000}`)
- Postgres plugin Railway lié via référence `${{Postgres.DATABASE_URL}}`
- Domaine généré : `filum-production-07bb.up.railway.app`

**Variables d'env Railway**
Toutes en lowercase (ADR-010) :
```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
backend_base_url       = https://filum-production-07bb.up.railway.app
frontend_base_url      = http://localhost:5173 (à update quand frontend déployé)
cors_origins           = ["http://localhost:5173"]
debug                  = false
```

`google_*`, `wayback_api_key`, `duckdb_path`, `api_v1_prefix`, `database_pool_size`, `database_max_overflow` : non configurés, defaults dans `config.py` suffisent.

**Conséquences**
- 1 fichier workflow en moins (`cd.yml` supprimé)
- Pas de secrets Railway dans GitHub Actions à gérer
- Logs de déploiement dans le dashboard Railway (meilleure UX que GHA pour ce cas)
- Migrations Alembic auto-exécutées au boot via le `CMD` Docker
- Le port dynamique impose un patch Dockerfile (`${PORT:-8000}`)
- La référence Postgres expose un URL sans `+asyncpg` → un `field_validator` dans `config.py` coerce automatiquement (`postgresql://` → `postgresql+asyncpg://`)
- Si on veut un jour un workflow déclencheur (release tags, smoke tests post-deploy), il faudra le réécrire depuis zéro avec le CLI Railway

**Validation**
```
curl https://filum-production-07bb.up.railway.app/health
→ {"status":"ok","version":"0.1.0"}

curl https://filum-production-07bb.up.railway.app/health/database
→ {"status":"ok","database":"connected"}
```

---

## ADR-016 — Graphe interactif D3 + relation `Source.parent_source_id`

**Date** : 2026-05

**Contexte**
La vision (`.docs/00-vision.md` lignes 50-59) et le product spec (`.docs/01-product-spec.md` lignes 96-101) promettent une "carte interactive des sources" inspirée de Pappers et Obsidian comme l'un des trois angles d'effet wow du MVP. La page publique livrée ne montrait qu'une liste accordion plate. Par ailleurs la "structure du raisonnement" (qui cite qui) n'était pas matérialisée en BDD.

**Options envisagées**
- Bibliothèque tierce type `vis-network` ou `cytoscape.js` (rejetée : poids + opacité du rendu, contrôle fin du design system difficile)
- Rendu statique côté serveur via Mermaid ou Graphviz (rejetée : pas d'interaction, pas de drag/zoom, valeur perçue inférieure)
- **D3.js v7 force-directed simulation + composant Svelte 5 dédié** (retenue)
- Stocker la lineage des sources en BDD via `Source.parent_source_id` (FK self-référente), pour que le graphe soit data-driven et que la "provenance/lineage" du projet soit matérialisée (retenue)

**Justifications**
- D3 v7 déjà installé en dépendance directe (avec `@types/d3`) → pas de nouvelle dette technique
- Contrôle fin du rendu (couleurs design system, taille par `authority_level`, halo pivot, dimming au hover, animation cascade) impossible avec une lib clé-en-main sans surcharger
- `parent_source_id` matérialise la promesse "structure du raisonnement" et permet une visualisation hiérarchique (sources de premier niveau près du centre, sources de second niveau en périphérie, plus petites, reliées en pointillés à leur parent)
- Compatible CSR-only (`ssr=false` dans `+layout.ts`) → pas besoin de guard browser

**Implémentation**
- Migration Alembic 003 : `op.add_column('sources', 'parent_source_id')` nullable + index
- `app/models/source.py` : champ + relationship auto-référentielle `parent`
- `app/schemas/source.py` : champ exposé sur `SourceBase`/`Create`/`Update`/`Response`
- `apps/frontend/src/lib/api/types.ts` : `Source.parent_source_id: string | null`
- `apps/frontend/src/lib/components/SourceGraph.svelte` (~310 lignes) : simulation D3, drag, zoom/pan/reset, cascade, légende, ResizeObserver
- `apps/frontend/src/lib/components/SourceDetailPanel.svelte` (~140 lignes) : side panel desktop / bottom sheet mobile, Escape, navigation vers le parent
- `apps/frontend/src/lib/utils/source-colors.ts` : single source of truth des couleurs (réutilisée par `SourceTypeBadge`)
- Seed `apps/backend/app/scripts/seed_demo.py` : remplace le placeholder par 14 sources réelles sur la neuroscience de la mémoire + 6 arêtes `parent_source_id`. Nouveau slug `memoire-et-cerveau` ; l'ancienne fiche `filum-demo` reste en BDD (orpheline mais signée) pour ne pas casser une éventuelle URL externe

**Garantie cryptographique**
La payload canonical_hash signée par `CardService.publish_card` (et vérifiée par `verify_card`) **N'inclut PAS** `parent_source_id`. La relation de citation est purement structurelle / graphique. Les signatures Ed25519 existantes sur les fiches déjà publiées restent valides après la migration.

**Conséquences**
- Page publique enfin alignée avec la vision : graphe au-dessus de la fold, panneau latéral au clic, sources de sources en périphérie, identité visuelle cohérente
- +1 migration (003), +3 fichiers frontend, +1 utilitaire de couleurs
- Bundle Vercel +80 KB minifié (d3 force/drag/zoom/selection) — acceptable pour MVP, tree-shaking actif
- L'index `ix_sources_parent_source_id` accélère la résolution d'éventuelles requêtes "qui cite X ?"
- Aucun changement de comportement runtime sur les endpoints existants ; tests existants non impactés (le champ est nullable et optionnel)

## ADR-018 — OpenGraph dynamique avec Pillow (backend)

**Date** : 2026-05-13

**Contexte**
Les fiches publiques avaient des meta tags `og:title`, `og:description`, mais pas `og:image`. Les aperçus de liens sur les réseaux (Twitter/X, Discord, LinkedIn) et les moteurs IA (Perplexity, SearchGPT) affichaient un lien nu sans visuel. Le développeur demande d'implémenter les images OG dynamiques.

**Options envisagées**
- `@vercel/og` / Satori + resvg-js côté frontend (SvelteKit server endpoint) — rejeté car nécessite `@sveltejs/adapter-vercel` explicite et dépendances lourdes (satori, resvg-js)
- Service externe comme `og-image.vercel.app` (rejeté : dépendance tierce, pas de contrôle)
- Backend Python avec Pillow (retenue)

**Justifications**
- Pillow est simple, stable, sans runtime complexe (pas de navigateur headless, pas de WASM)
- Railway (backend) peut servir des images PNG statiques sans problème
- Police DejaVu Serif disponible sur Ubuntu/Railway (fallback interne si absente)
- Le endpoint `GET /api/v1/og?title=&creator=` est simple à cache-CDN (Cache-Control à ajouter plus tard)
- Permet un contrôle fin du design (couleurs, typo, layout) sans passer par du HTML+CSS+rendering

**Implémentation**
- `app/services/og_image.py` : `generate_og_image(title, creator)` → bytes PNG (Pillow)
- Fond sombre #0F172A (slate-900), accent #3B82F6 (blue-500), texte blanc
- Titre centré en DejaVu Serif Bold 48px, wrapper à 30 caractères
- Créateur en subtitle 24px, footer "filum.app — bibliographie vérifiable"
- `app/api/v1/endpoints/og.py` : route `GET /og` avec paramètres `title` (required) et `creator` (optional)
- Frontend : `og:image` et `twitter:image` pointent vers `{API_BASE}/api/v1/og?title=...&creator=...`

**Conséquences**
- +1 dépendance backend : `Pillow>=12.2.0` (~12 MB installé)
- +2 fichiers backend (service + endpoint)
- +1 fichier frontend modifié (meta tags sur la fiche publique)
- Image générée à la volée (pas de cache pour l'instant — à ajouter si le trafic augmente)
- Les polices DejaVu sont présentes sur Railway (Ubuntu) et en local — si absentes, Pillow utilise un fallback

## ADR-019 — La signature porte sur le lien créateur·ice ↔ contenu, plus sur la fiche bibliographique

**Date** : 2026-05-14

**Contexte**
Le MVP signe chaque fiche bibliographique au moment du `publish` : `canonical_hash` + `signature` Ed25519 sur `BiblioCard` (titre + sources + métadonnées canonicalisées via RFC 8785). Conséquence implicite acceptée jusqu'ici : la fiche devient immuable ; toute modification invaliderait la signature et nécessiterait dé-publication / re-publication, donc en pratique elle est figée.

L'utilisateur (Mathias) constate que ce modèle est contre-productif :
- Les fiches sont des documents vivants. Corriger une coquille, ajouter une source plus tard, raffiner une annotation : autant de gestes légitimes que l'immuabilité bloque.
- Ce qui compte vraiment, ce que les usagers tiers veulent vérifier, ce n'est pas la composition exacte de la bibliographie à un instant T mais : « tel·le créateur·ice revendique-t-il·elle bien tel contenu original (vidéo, article, podcast) à telle date ? »

**Décision**
La crypto Ed25519 / SHA-256 / RFC 8785 est conservée mais l'objet signé change. **Un seul type d'objet attesté** : le **lien créateur·ice ↔ contenu**, sous forme d'un triplet `(creator_id, content_url, attested_at)`, signé. Cela prouve « tel·le créateur·ice revendique telle URL comme contenu mien à telle date ».

Les fiches bibliographiques (`BiblioCard`) **redeviennent mutables** : modification libre tant que le créateur est authentifié. Suppression des colonnes `canonical_hash`, `signature`, `signed_at` du contrat de signature (`published_at` peut rester pour l'horodatage UX, sans rôle cryptographique).

Le **profil créateur·ice n'est PAS signé** en tant que tel. Seule sa clé publique est exposée publiquement pour permettre la vérification des attestations qu'il·elle a émises. L'identité Filum reste portée par l'authentification (Google OAuth) et la possession démontrée de la clé privée.

**Justifications**
- Aligne le produit sur le besoin réel (vérifier la paternité d'un contenu) plutôt que sur un fantasme d'immuabilité bibliographique
- Décolle la crypto du flux d'édition : on peut éditer une fiche autant qu'on veut sans rien resigner
- Simplifie le modèle mental : « ce que Filum garantit, c'est mon lien à un contenu, pas mon brouillon de bibliographie »
- Modèle à un seul type d'objet signé : plus simple à implémenter et à expliquer qu'un système à deux types (profil + content_link)
- Ouvre la voie naturelle à la collaboration sur les fiches (Phase 2)

**Conséquences code (à implémenter dans PR backend dédiée, non incluse dans #31)**
- Nouvelle table `content_attestations` : `(id, user_id, content_url, attested_at, canonical_hash, signature)`. Unicité sur `(user_id, content_url)` à discuter (un même créateur revendique-t-il une URL une seule fois, ou peut-il la re-revendiquer ultérieurement ?)
- Suppression de la signature sur `biblio_cards` : migration `006_remove_card_signature` qui dropte `canonical_hash`, `signature`, `signed_at` (et garde `published_at` sans rôle crypto)
- Endpoint `POST /cards/{id}/publish` redevient un simple flip de statut, plus de crypto
- Nouvel endpoint `POST /attestations/content` (création) + `GET /attestations/{id}/verify` (vérification publique)
- Liaison `BiblioCard.content_url` → `ContentAttestation` : à exposer dans la fiche publique pour afficher l'attestation correspondante
- Refonte de `seed_demo.py` : plus de re-signature de fiche, à la place une attestation de contenu pour la vidéo démo « Mémoire et cerveau »
- Frontend types `BiblioCard`/`PublicCard` : supprimer `canonical_hash`/`signature`/`signed_at` (ou garder `null`-ables le temps de la migration). Ajouter un type `ContentAttestation`
- Tests : `test_canonical_hash.py` / `test_crypto.py` rebasculer sur les attestations de contenu
- Specs `.docs/01..04, 08` : sections crypto à réécrire (objet signé, schéma, API)
- `agent/PITFALLS.md` item 1.3 : la règle « ne jamais modifier le payload signé » s'applique maintenant aux attestations de contenu

**Conséquences user-facing (incluses dans PR #31)**
- Page `/security` réécrite : un seul type d'objet signé expliqué (le lien créateur·ice ↔ contenu)
- Pages `/`, `/features`, `/about`, `/roadmap` : reformulation « attestation de contenu », plus de mention d'immuabilité de fiche
- Fiche publique `@{creator}/{card}` : footer ne montre plus la signature hash de la fiche ; affiche « Contenu revendiqué par son créateur·ice » avec lien vers `/security`. La date affichée est `published_at` (sans rôle crypto)
- FAQ « Puis-je modifier une fiche publiée ? » supprimée (réponse devient « oui »)

**Transition**
La prod tourne encore avec l'ancien schéma. Le frontend de PR #31 ne *lit* plus `card.signature` / `card.signed_at` ; les champs restent renvoyés par l'API mais ignorés. Pas de casse côté prod. La PR backend dédiée fera la migration descendante propre et ajoutera la table `content_attestations`.

---

<!--
## ADR-NNN — Titre court

**Date** : YYYY-MM

**Contexte**
...

**Options envisagées**
...

**Justifications**
...

**Conséquences**
...
-->


## ADR-017 - Itu00e9ration 2 : indicateurs structuru00e9s, extraits, SSR fiche publique, refonte panneau

**Date** : 2026-05-12

**Contexte**

Apru00e8s la du00e9mo de neuroscience (itu00e9ration 1), quatre faiblesses bloquaient un usage MVP cru00e9dible : (1) un cube gu00e9nu00e9rique en guise de logo, (2) une cartographie sans nom d'auteur et un panneau collu00e9 au bord droit, (3) un jugement implicite via 'Autoritu00e9 u00e9levu00e9e/moyenne/faible' qui n'a aucun fondement vu00e9rifiable, (4) une page publique 100 % CSR, donc invisible aux bots SEO et aux moteurs IA (Perplexity, SearchGPT, Claude).

**Du00e9cisions**

1. **Indicateurs typu00e9s par type de source** plutu00f4t qu'un niveau d'autoritu00e9 fourre-tout. Colonnes flat : 'citations_count', 'impact_factor', 'subscribers_count', 'views_count'. Affichu00e9es sous forme de chips neutres. La colonne 'authority_level' n'est plus utilisu00e9e par l'UI mais reste en base (pas de migration destructive, et pas d'impact sur le 'canonical_hash').
2. **Table du00e9diu00e9e 'source_excerpts'** (FK CASCADE, position, text, suggested_by_ai). Pru00e9fu00e9ru00e9e u00e0 un JSONB sur 'sources' pour : indexabilitu00e9, contrainte 'NOT NULL' sur le texte, u00e9volution future vers un picker IA sans migration de schema.
3. **'conflict_of_interest' TEXT nullable**. Affichu00e9 _uniquement_ s'il est renseignu00e9 (jamais 'Aucun conflit') pour ne pas du00e9nigrer par omission.
4. **Renommage 'Pivot' -> 'Source clu00e9'** avec tooltip 'Source structurante du raisonnement'. 'Pivot' restait jargonnant et asymu00e9trique vis-u00e0-vis du reste de l'interface.
5. **SSR uniquement sur la fiche publique** ('+page.ts' avec 'ssr = true', surcharge le 'ssr = false' du '+layout.ts'). Le D3 est chargu00e9 cu00f4tu00e9 client via dynamic import ; le rendu serveur produit le HTML statique (sources + JSON-LD) que les bots et IA peuvent lire sans exu00e9cuter JS.
6. **JSON-LD Article + Person + citations[]** dans '<svelte:head>'. Crucial pour le GEO : Perplexity, SearchGPT, Claude.ai lisent prioritairement le JSON-LD avant le DOM.
7. **Panneau de du00e9tail ancru00e9 au nu0153ud cliquu00e9** plutu00f4t que collu00e9 au bord droit de la fenu00eatre. Largeur ru00e9duite (320px), positionnement contextuel, fallback bottom-sheet sur mobile (< 600px).

**Non-du00e9cisions (explicit)**

- Le 'canonical_hash' payload n'est PAS modifiu00e9. Les nouveaux champs restent hors signature pour pru00e9server la validitu00e9 des fiches du00e9ju00e0 publiu00e9es.
- Pas de picker IA pour les excerpts dans cette itu00e9ration : 'suggested_by_ai' est seedu00e9 u00e0 'false', le champ est lu00e0 pour la future feature.
- Pas de mode privu00e9 ni connectivitu00e9 Zotero/Obsidian/Notion : seulement un doc spec ('.docs/09-private-mode-and-integrations.md').

**Consu00e9quences**

- Toutes les fiches du00e9ju00e0 publiu00e9es restent vu00e9rifiables : le payload signu00e9 est inchangu00e9.
- La page publique devient indexable par Google et lisible par les moteurs IA.
- L'ajout futur d'un champ visible doit systu00e9matiquement se demander : 'rentre-t-il dans la signature ou pas ?' (par du00e9faut, non).
