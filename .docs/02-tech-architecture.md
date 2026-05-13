# 02 — Architecture technique

> Ce document décrit les choix d'architecture du projet : stack, structure, déploiement.

---

## Vue d'ensemble

```
                  ┌──────────────────────┐
                  │   Utilisateur web    │
                  └──────────┬───────────┘
                             │ HTTPS
                  ┌──────────▼───────────┐
                  │  Frontend SvelteKit  │   Vercel ou Netlify
                  │  (SSR + îlots Svelte)│
                  └──────────┬───────────┘
                             │ REST/JSON
                  ┌──────────▼───────────┐
                  │  Backend FastAPI     │   Railway
                  │  (Python 3.12)       │
                  └──┬───────────────┬───┘
                     │               │
          ┌──────────▼──────┐  ┌────▼──────────────────┐
          │  PostgreSQL     │  │  Services externes    │
          │  (transactionnel│  │  - Wayback Machine    │
          │   user, fiches, │  │  - Google OAuth       │
          │   sources)      │  │  - (futur) ORCID, etc.│
          └──────────┬──────┘  └───────────────────────┘
                     │
          ┌──────────▼──────┐
          │  DuckDB         │   Local dans le conteneur backend
          │  (analytics,    │   Données chargées depuis Postgres
          │   modèles dbt)  │
          └─────────────────┘
```

---

## Choix de stack — résumé et justifications

### Backend : Python 3.12 + FastAPI

**Pourquoi Python** : maîtrise par les LLMs maximale (efficacité du développement assisté IA), écosystème data extrêmement riche (DuckDB, dbt, Pandas, numpy si besoin), aligné avec un portfolio Data Engineer.

**Pourquoi FastAPI** : async natif, validation Pydantic intégrée, génération automatique d'une doc OpenAPI, performant. Standard de facto pour les APIs Python modernes.

**Versions et libs principales** :
- Python 3.12+
- FastAPI 0.110+
- SQLAlchemy 2.x en mode async
- Alembic pour les migrations
- Pydantic v2 pour la validation
- `cryptography` pour Ed25519 et SHA-256
- `httpx` pour les appels HTTP sortants (asynchrone)
- `uv` comme package manager (ultra rapide, remplace pip)

### Bases de données : PostgreSQL + DuckDB

**Pourquoi PostgreSQL pour le transactionnel** : standard absolu, écosystème mûr, support natif des UUIDs, jsonb, types riches. Hébergé gratuitement sur Railway.

**Pourquoi DuckDB pour l'analytique** :
- C'est la techno data analytics qui a le plus monté en visibilité depuis 2023
- Idéal pour les requêtes sur le graphe de citations, les agrégations par type de source, les analytics par créateur
- Embedded (pas de serveur séparé à déployer)
- Lit/écrit Parquet et Postgres directement
- Excellent pour le portfolio Data Engineer

**Pattern** : les données transactionnelles vivent dans Postgres. À intervalle régulier (cron, ou trigger), un job ETL charge ces données dans DuckDB sous forme de tables analytiques optimisées. dbt transforme ensuite ces tables en marts/vues prêtes à consommer.

### Transformations data : dbt-core sur DuckDB

dbt (data build tool) est le standard moderne pour les transformations versionnées et testées. Sur DuckDB en local, c'est gratuit, rapide, et signe fort sur un portfolio Data Engineer.

**Modèles dbt prévus** :
- `staging/` : extractions brutes depuis Postgres (sources, fiches, utilisateurs, événements)
- `marts/` : agrégations métier (statistiques par créateur, sources les plus citées, types de sources par contenu)
- `analytics/` : tables prêtes à consommer pour l'API ou les dashboards (top sources, graphe de filiation, etc.)

### Frontend : SvelteKit + TypeScript + Tailwind

**Pourquoi SvelteKit plutôt que Next.js** :
- Syntaxe plus claire et compacte
- Bundle JavaScript plus petit (pas de duplication HTML+JSON systématique)
- Excellent rendu serveur natif
- Maîtrisé par les LLMs (génération de code de qualité)
- Moins de "magie" cachée, plus facile à debugger

**Pourquoi Tailwind plutôt qu'une lib de composants** :
- Liberté de design totale (essentielle pour ce projet où l'esthétique compte)
- Performance optimale
- Maîtrisé par les LLMs

**Composants** : créés à la main au fur et à mesure, dans `apps/frontend/src/lib/components/`. Pas de framework UI (Bootstrap, Material, etc.).

### Crypto

- **Hash** : SHA-256 standard via `cryptography.hazmat.primitives.hashes`
- **Signature** : Ed25519 via `cryptography.hazmat.primitives.asymmetric.ed25519`
- **Génération de paires de clés** : à la création du compte utilisateur
- **Stockage des clés privées** : chiffrées au repos en base, déchiffrées en mémoire au moment de la signature. Clé de chiffrement maître stockée dans une variable d'environnement (en phase 1 — KMS prévu pour phase 3).

### Archivage : Internet Archive Wayback Machine

**API** : `https://web.archive.org/save/<url-à-archiver>` (gratuit, sans authentification pour usage modéré)

**Pattern** : à chaque ajout de source, un job asynchrone (Celery ou simplement `asyncio.create_task`) lance la requête. La réponse contient l'URL d'archive Wayback, qui est stockée dans la table `sources`.

**Limites** : Wayback rate limite à ~10-15 requêtes/minute. Pour un MVP en phase 1, c'est largement suffisant. À surveiller en phase 2.

### OAuth Google

- Lib : `authlib` (Python) — moderne, async-compatible
- Scope demandé : `openid email profile` uniquement
- Pas de stockage du token Google après l'inscription (sauf besoin futur d'accès aux APIs Google)

---

## Structure du code

Voir [`CLAUDE.md`](../CLAUDE.md) section "Structure attendue du projet" pour le détail.

Résumé :

```
apps/
├── backend/     # FastAPI
├── frontend/    # SvelteKit
└── analytics/   # dbt project
```

Mono-repo simple, géré avec `make` à la racine.

---

## Sécurité — pratiques minimales

- **Variables d'environnement** : jamais en dur, `.env` ignoré par Git, `.env.example` à jour
- **Validation entrante** : Pydantic v2 partout côté backend, Zod ou validation manuelle côté frontend
- **CORS** : restreint à l'origine du frontend en production
- **CSP** : Content Security Policy stricte sur les pages publiques
- **Rate limiting** : `slowapi` côté FastAPI sur les endpoints sensibles (création de fiche, ajout de source)
- **Audit logs** : table `audit_events` qui log toutes les actions sensibles (création, modification, suppression)
- **HTTPS** : Railway et Vercel/Netlify l'imposent par défaut
- **Stockage des secrets utilisateur** : clés privées chiffrées au repos avec une clé maître (Fernet symétrique), clé maître en env var
- **SQL injection** : impossible avec SQLAlchemy ORM, jamais de requêtes formatées par string

---

## Performance — pratiques minimales

- **Cache HTTP** : pages publiques mises en cache CDN (Vercel/Netlify) pendant 60 secondes minimum
- **Lazy loading** : graphe interactif chargé après le SSR initial
- **Bundle size** : surveillance avec `vite-bundle-visualizer` — objectif < 200 KB gzippé pour le bundle initial
- **Images** : avatars optimisés à l'upload (max 256x256, WebP)
- **DB indexes** : index sur les colonnes fréquemment requêtées (`users.slug`, `biblio_cards.slug`, `biblio_cards.creator_id`, `sources.biblio_card_id`)

---

## Observabilité

En MVP, minimal :
- Logs structurés côté backend (`structlog`)
- Erreurs frontend dans la console (pas de Sentry en MVP — à ajouter en phase 2)
- Métriques de base (uptime, latence API) via Railway/Vercel dashboards

En phase 2, ajouter :
- Sentry pour le tracking d'erreurs
- Plausible Analytics (privacy-friendly) pour les analytics web

---

## Déploiement

### Phase MVP (semaine 1-2)

- **Backend** : Railway. Tier gratuit ou Hobby ($5/mois). Postgres inclus. CI/CD automatique sur push GitHub.
- **Frontend** : Vercel (recommandé pour SvelteKit, gratuit). Netlify est une alternative équivalente.
- **Domaine** : `filum.app` à acheter (~$15/an chez Cloudflare Registrar)

### Phase 3 — production souveraine

- **Migration prévue** : Scaleway (Paris). Conteneurs Docker, Postgres managé, stockage objet pour les snapshots propres.
- **Argumentaire** : conformité RGPD native, souveraineté européenne pour les institutions.

---

## Coûts estimés en phase MVP

- Railway : 0-5 $/mois
- Vercel ou Netlify : 0 $/mois (tier gratuit)
- Cloudflare Registrar (domaine) : ~15 $/an
- Google OAuth : 0 $
- Internet Archive : 0 $

**Total** : < 10 $/mois en phase 1.

---

## Intégrations externes — résumé

| Service | Phase | Coût | Limite |
|---|---|---|---|
| Google OAuth | MVP | 0 € | Pratiquement illimité |
| Internet Archive Wayback | MVP | 0 € | ~10-15 req/min |
| Railway hosting | MVP | 0-5 €/mois | 500h/mois tier gratuit |
| Vercel hosting | MVP | 0 € | 100 GB bande passante/mois |
| **(phase 2)** ORCID OAuth | Phase 2 | 0 € | Illimité (académique) |
| **(phase 2)** YouTube OAuth | Phase 2 | 0 € | Quotas Google API |
| **(phase 3)** C2PA Conformance Program | Phase 3 | ~10 000 €/an | — |
| **(phase 3)** Scaleway | Phase 3 | Variable | — |
| **(phase 3)** TSA eIDAS (Universign/Certinomis) | Phase 3 | ~0,10 €/horodatage | — |

---

## Diagramme de séquence — création d'une fiche

```
Léa            Frontend         Backend         Postgres        Wayback
 │                │                │                │              │
 │── click "publier"──────────────>│                │              │
 │                │                │                │              │
 │                │── POST /api/biblio-cards ──────>│              │
 │                │                │                │              │
 │                │                │── INSERT user (si nouveau) ──>│
 │                │                │── INSERT biblio_card ────────>│
 │                │                │                │              │
 │                │                │── pour chaque source : INSERT ─>│
 │                │                │                │              │
 │                │                │── async: POST /save/<url>───────>│
 │                │                │<── archive URL ──────────────────│
 │                │                │── UPDATE source.archive_url ─>│
 │                │                │                │              │
 │                │                │── compute hash + sign ────────│
 │                │                │── UPDATE biblio_card.hash ───>│
 │                │                │                │              │
 │                │<── 200 OK + slug ──────────────│              │
 │<── redirection vers /@lea-c/slug─────────────────│              │
```

---

## Sauvegarde de la base de données

Railway offre un dump PostgreSQL via son dashboard (plan Hobby) :
- Aller sur le dashboard Railway → service PostgreSQL → "Dump" ou "Backup".
- Le dump est un fichier `.dump` téléchargeable.

En CLI avec la chaîne de connexion :
```bash
pg_dump --no-owner --clean "$DATABASE_URL" > filum_backup_$(date +%Y-%m-%d).sql
```

**Fréquence recommandée** : hebdomadaire en phase MVP (manuel). Si le nombre d'utilisateurs grandit, basculer vers un backup automatisé (`pg_cron` ou script GitHub Actions avec `pg_dump`).

**Restauration** :
```bash
psql "$DATABASE_URL" < filum_backup_2026-05-13.sql
```

---

## Stratégie de test

- **Backend** : `pytest` avec `pytest-asyncio`. Couverture cible : tous les endpoints, toutes les fonctions crypto, l'extraction de métadonnées.
- **Frontend** : `vitest` pour les fonctions utilitaires, tests E2E avec Playwright en phase 2.
- **Migrations** : test automatique de l'aller-retour (up puis down) sur chaque migration.
- **CI** : GitHub Actions, exécution des tests à chaque push.

---

*Pour le détail du modèle de données, voir [`03-data-model.md`](./03-data-model.md).*
*Pour les endpoints API, voir [`04-api-design.md`](./04-api-design.md).*
