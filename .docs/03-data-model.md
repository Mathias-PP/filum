# 03 — Modèle de données

> Schéma de base de données, modèles SQLAlchemy, et structure des tables dbt.

---

## Schéma PostgreSQL — vue d'ensemble

```
┌─────────────────┐       ┌──────────────────┐       ┌────────────────┐
│     users       │       │   biblio_cards   │       │    sources     │
├─────────────────┤       ├──────────────────┤       ├────────────────┤
│ id (uuid PK)    │◄──────│ creator_id (FK)  │       │ id (uuid PK)   │
│ google_sub      │       │ id (uuid PK)     │◄──────│ biblio_card_id │
│ email           │       │ slug             │       │ position       │
│ slug (unique)   │       │ title            │       │ url            │
│ display_name    │       │ description      │       │ title          │
│ description     │       │ canonical_url    │       │ authors        │
│ avatar_url      │       │ platform         │       │ published_at   │
│ public_key      │       │ status           │       │ source_type    │
│ encrypted_priv  │       │ content_hash     │       │ annotation     │
│ created_at      │       │ signature        │       │ is_pivot       │
│ updated_at      │       │ signed_at        │       │ archive_url    │
└─────────────────┘       │ published_at     │       │ archive_status │
                          │ created_at       │       │ created_at     │
                          │ updated_at       │       └────────────────┘
                          └──────────────────┘
                                  │
                                  │
                          ┌───────▼──────────┐
                          │  audit_events    │
                          ├──────────────────┤
                          │ id (uuid PK)     │
                          │ user_id (FK)     │
                          │ entity_type      │
                          │ entity_id        │
                          │ event_type       │
                          │ event_data (jsonb)│
                          │ created_at       │
                          └──────────────────┘
```

---

## Table : `users`

Représente un créateur Filum.

| Colonne | Type | Description |
|---|---|---|
| `id` | `uuid` PK | Identifiant interne |
| `google_sub` | `text` unique | Identifiant Google OAuth (claim `sub`) |
| `email` | `text` unique | Email Google (sensible — accès restreint) |
| `slug` | `text` unique | Identifiant public (`lea-c`, `hugo-decrypte`...) |
| `display_name` | `text` | Nom affiché (`Léa Caron`) |
| `description` | `text` nullable | Description courte (max 200 chars) |
| `avatar_url` | `text` nullable | URL avatar (par défaut généré côté frontend) |
| `public_key` | `bytea` | Clé publique Ed25519 (32 bytes) |
| `encrypted_private_key` | `bytea` | Clé privée Ed25519 chiffrée avec la clé maître |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |

**Index** : `users_slug_idx` sur `slug`, `users_google_sub_idx` sur `google_sub`, `users_email_idx` sur `email`.

**Contraintes** :
- `slug` doit matcher la regex `^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$` (slug URL-friendly, 3-40 chars)
- `email` non-nullable, format email valide
- `public_key` exactement 32 bytes

---

## Table : `biblio_cards`

Représente une fiche bibliographique pour un contenu.

| Colonne | Type | Description |
|---|---|---|
| `id` | `uuid` PK | |
| `creator_id` | `uuid` FK → users.id | Créateur de la fiche |
| `slug` | `text` | Slug local au créateur (`arctique-2026`) |
| `title` | `text` | Titre du contenu |
| `description` | `text` nullable | Description courte (max 500 chars) |
| `canonical_url` | `text` nullable | URL du contenu original (YouTube, blog...) |
| `platform` | `text` nullable | `youtube`, `podcast`, `blog`, `x`, `bluesky`, `other` |
| `status` | `text` | `draft`, `published`, `archived` |
| `content_hash` | `bytea` nullable | SHA-256 du contenu canonique de la fiche (calculé à la publication) |
| `signature` | `bytea` nullable | Signature Ed25519 (64 bytes) |
| `signed_at` | `timestamptz` nullable | Date de signature |
| `published_at` | `timestamptz` nullable | Date de publication |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |

**Index** : `biblio_cards_creator_slug_idx` unique sur `(creator_id, slug)`, `biblio_cards_status_idx` sur `status`.

**Contraintes** :
- `slug` matche la regex `^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$` (3-80 chars)
- Une fiche publiée doit avoir `content_hash`, `signature`, `signed_at`, `published_at` tous renseignés (vérifié au niveau application + check constraint)
- `status` IN (`draft`, `published`, `archived`)

**URL publique** : `https://filum.app/@<users.slug>/<biblio_cards.slug>`

---

## Table : `sources`

Représente une source citée dans une fiche.

| Colonne | Type | Description |
|---|---|---|
| `id` | `uuid` PK | |
| `biblio_card_id` | `uuid` FK → biblio_cards.id | |
| `position` | `int` | Ordre de la source dans la fiche (1, 2, 3...) |
| `url` | `text` | URL de la source |
| `title` | `text` | Titre extrait ou saisi manuellement |
| `authors` | `text` nullable | Auteurs (texte libre) |
| `published_at` | `date` nullable | Date de publication de la source |
| `source_type` | `text` | `peer-reviewed`, `institutional`, `press`, `original`, `other` |
| `annotation` | `text` nullable | "Pourquoi je cite cette source" (max 500 chars) |
| `is_pivot` | `boolean` default `false` | Source structurante du raisonnement |
| `archive_url` | `text` nullable | URL Wayback Machine de l'archive |
| `archive_status` | `text` | `pending`, `archived`, `failed` |
| `archive_attempted_at` | `timestamptz` nullable | |
| `archive_completed_at` | `timestamptz` nullable | |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | |

**Index** : `sources_biblio_card_id_idx`, `sources_url_idx` (pour la détection de doublons), `sources_archive_status_idx` (pour les jobs background).

**Contraintes** :
- `position` >= 1
- `source_type` IN (`peer-reviewed`, `institutional`, `press`, `original`, `other`)
- `archive_status` IN (`pending`, `archived`, `failed`)
- `(biblio_card_id, position)` unique

---

## Table : `audit_events`

Log des actions sensibles. Append-only.

| Colonne | Type | Description |
|---|---|---|
| `id` | `uuid` PK | |
| `user_id` | `uuid` FK → users.id, nullable | User qui a déclenché l'événement |
| `entity_type` | `text` | `biblio_card`, `source`, `user` |
| `entity_id` | `uuid` | Identifiant de l'entité concernée |
| `event_type` | `text` | `create`, `update`, `delete`, `publish`, `archive_source`, `login`... |
| `event_data` | `jsonb` | Détails de l'événement |
| `created_at` | `timestamptz` | |

**Index** : `audit_events_user_id_idx`, `audit_events_entity_idx` sur `(entity_type, entity_id)`, `audit_events_created_at_idx`.

---

## Calcul du `content_hash` (canonicalisation)

Pour qu'une fiche soit signable, son contenu doit être canonicalisé de manière déterministe avant d'être hashé.

**Algorithme** :
1. Construire un objet JSON avec les champs canoniques (dans cet ordre exact) :
   ```json
   {
     "creator_slug": "lea-c",
     "card_slug": "arctique-2026",
     "title": "Pourquoi...",
     "description": "...",
     "canonical_url": "https://...",
     "platform": "youtube",
     "sources": [
       {
         "position": 1,
         "url": "https://...",
         "title": "...",
         "authors": "...",
         "published_at": "2022-08-11",
         "source_type": "peer-reviewed",
         "annotation": "...",
         "is_pivot": true,
         "archive_url": "https://web.archive.org/..."
       },
       ...
     ]
   }
   ```
2. Sérialiser en JSON canonique selon RFC 8785 (JCS) — clés triées, pas d'espace superflu, encoding UTF-8 strict
3. Calculer SHA-256 de la chaîne UTF-8 résultante
4. Stocker dans `biblio_cards.content_hash`

**Vérification** : la signature peut être vérifiée publiquement en recalculant le hash à partir des données API et en vérifiant la signature avec la clé publique du créateur.

**Implémentation** : utiliser la lib `rfc8785` Python ou réimplémenter — c'est court.

---

## Schéma DuckDB / dbt

DuckDB stocke des copies analytiques des données Postgres, chargées périodiquement. Structure organisée en couches dbt standard :

### Couche `staging`

Réplique 1:1 des tables Postgres principales (légère normalisation, typage).

- `stg_users` : un par utilisateur
- `stg_biblio_cards` : une par fiche
- `stg_sources` : une par source
- `stg_audit_events` : un par événement

### Couche `marts`

Agrégations métier.

- `mart_creator_stats` : un par créateur (nombre de fiches, sources, citations entrantes/sortantes, types de sources dominants)
- `mart_card_stats` : un par fiche (nombre de sources, nombre de peer-reviewed, etc.)
- `mart_source_popularity` : un par URL unique citée (combien de fois citée, par combien de créateurs distincts, types de créateurs)
- `mart_lineage_edges` : edges du graphe de citations entre fiches (préparation pour le graphe descendant futur)

### Couche `analytics`

Tables prêtes à consommer.

- `analytics_top_sources` : top 100 sources par citation
- `analytics_creator_leaderboard` : top créateurs par activité
- `analytics_source_type_distribution` : distribution des types de sources par fiche et par créateur

### Fréquence de refresh

- En MVP : refresh manuel via `make analytics-refresh` (lance un script Python qui charge Postgres → DuckDB et exécute `dbt run`)
- En phase 2 : refresh automatique toutes les heures via un cron ou un scheduler simple (Prefect ou Dagster local — choix à arbitrer)

---

## Migration Alembic — première migration

La migration initiale crée les 4 tables ci-dessus avec leurs index et contraintes. Elle doit être réversible (`downgrade` implémenté).

Voir [`06-roadmap.md`](./06-roadmap.md) jour 1 pour les détails d'implémentation.

---

## Évolutions prévues du schéma

Pour la phase 2 :
- Ajout d'une table `external_accounts` (un user peut lier plusieurs comptes externes : YouTube, X, ORCID, Mastodon)
- Ajout d'une table `card_views` pour les analytics simples (anonymisées)
- Ajout d'une table `source_relationships` pour le lineage descendant (quand un créateur déclare qu'une source en cite une autre)

Pour la phase 3 :
- Intégration de C2PA : ajout de colonnes `c2pa_manifest` et `c2pa_certificate_chain` sur `biblio_cards`
- Ajout d'une table `time_stamps` pour les horodatages qualifiés eIDAS
- Ajout d'une table `verifiable_credentials` pour les niveaux d'identité supérieurs

Toutes ces évolutions sont conçues pour ne pas casser la rétrocompatibilité du modèle MVP.

---

*Pour l'API qui expose ces données, voir [`04-api-design.md`](./04-api-design.md).*
