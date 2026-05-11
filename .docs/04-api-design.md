# 04 — Design de l'API

> Endpoints REST exposés par le backend FastAPI. Conventions, contrats, exemples.

---

## Principes généraux

- **REST classique**, pas GraphQL. Plus simple pour le MVP, plus de tooling existant.
- **JSON** systématiquement. Pas d'API HTML.
- **Versionnement** : préfixe `/api/v1/`. Évolutions cassantes feront `/api/v2/`.
- **Status codes HTTP standards** : 200, 201, 204, 400, 401, 403, 404, 422, 429, 500.
- **Format d'erreur unifié** : tous les errors retournent un JSON avec `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- **CORS** : seul l'origin du frontend est autorisé.
- **Rate limiting** : 60 req/min par IP en MVP, augmenté pour les utilisateurs authentifiés.

---

## Authentification

Toutes les routes mutables nécessitent l'authentification.

**Mécanisme** : OAuth Google → session côté backend → cookie HTTP-only sécurisé `filum_session` (JWT signé).

**Header alternatif** : `Authorization: Bearer <token>` pour les appels API depuis scripts (à venir en phase 2, en MVP seulement le cookie).

**Endpoints d'authentification** :

- `GET /api/v1/auth/login` — démarre le flux OAuth Google, redirige vers Google
- `GET /api/v1/auth/callback` — callback OAuth, crée la session, redirige vers le frontend
- `POST /api/v1/auth/logout` — invalide la session
- `GET /api/v1/auth/me` — retourne l'utilisateur courant si connecté, 401 sinon

---

## Endpoints publics (sans auth)

### `GET /api/v1/cards/{creator_slug}/{card_slug}`

Récupère une fiche bibliographique publique.

**Paramètres** :
- `creator_slug` : slug du créateur (ex: `lea-c`)
- `card_slug` : slug de la fiche (ex: `arctique-2026`)

**Réponse 200** :
```json
{
  "id": "uuid",
  "creator": {
    "slug": "lea-c",
    "display_name": "Léa Caron",
    "description": "Vulgarisatrice climat",
    "avatar_url": "https://...",
    "public_key": "base64..."
  },
  "slug": "arctique-2026",
  "title": "Pourquoi l'Arctique se réchauffe quatre fois plus vite que le reste du monde",
  "description": "...",
  "canonical_url": "https://youtube.com/watch?v=...",
  "platform": "youtube",
  "content_hash": "hex64...",
  "signature": "base64...",
  "signed_at": "2026-03-14T18:42:00Z",
  "published_at": "2026-03-14T18:42:00Z",
  "sources": [
    {
      "id": "uuid",
      "position": 1,
      "url": "https://...",
      "title": "Quadrupled Arctic amplification revealed in observations and models",
      "authors": "Rantanen et al.",
      "published_at": "2022-08-11",
      "source_type": "peer-reviewed",
      "annotation": "Source pivot du raisonnement...",
      "is_pivot": true,
      "archive_url": "https://web.archive.org/web/...",
      "archive_status": "archived"
    },
    ...
  ],
  "stats": {
    "total_sources": 11,
    "peer_reviewed": 6,
    "institutional": 3,
    "press": 1,
    "original": 1,
    "all_archived": true
  }
}
```

**Réponses d'erreur** :
- 404 si fiche inexistante ou non publiée

**Cache** : `Cache-Control: public, max-age=60, s-maxage=300`

---

### `GET /api/v1/users/{slug}`

Récupère la page-identité publique d'un créateur.

**Réponse 200** :
```json
{
  "slug": "lea-c",
  "display_name": "Léa Caron",
  "description": "Vulgarisatrice climat",
  "avatar_url": "https://...",
  "public_key": "base64...",
  "stats": {
    "total_cards": 12,
    "total_sources": 87,
    "first_published_at": "2025-09-01T...",
    "last_published_at": "2026-03-14T..."
  },
  "cards": [
    {
      "slug": "arctique-2026",
      "title": "...",
      "published_at": "2026-03-14T18:42:00Z",
      "total_sources": 11
    },
    ...
  ]
}
```

---

### `GET /api/v1/cards/{creator_slug}/{card_slug}/verify`

Vérification cryptographique de la signature d'une fiche.

**Réponse 200** :
```json
{
  "valid": true,
  "creator_slug": "lea-c",
  "card_slug": "arctique-2026",
  "content_hash": "hex64...",
  "signature": "base64...",
  "signed_at": "2026-03-14T18:42:00Z",
  "details": {
    "hash_algorithm": "SHA-256",
    "signature_algorithm": "Ed25519",
    "canonicalization": "RFC 8785 JSON Canonicalization Scheme"
  }
}
```

Si invalide :
```json
{
  "valid": false,
  "reason": "signature_mismatch" | "hash_mismatch" | "missing_signature",
  ...
}
```

---

### `GET /api/v1/cards/{creator_slug}/{card_slug}/og.png`

Génère dynamiquement une image OpenGraph (1200x630) pour le partage social.

**Contenu de l'image** :
- Titre de la fiche
- Nom du créateur + avatar
- Statistiques principales (4 chiffres)
- Mini-visualisation du graphe en arrière-plan
- Logo Filum

**Headers** : `Cache-Control: public, max-age=86400` (1 jour)

**Implémentation** : génération via Playwright ou via une lib Python comme `Pillow` (plus simple en MVP). Image cachée sur disque ou sur un objet store, regénérée à chaque republication.

---

## Endpoints authentifiés

### `POST /api/v1/cards` — créer une fiche en brouillon

**Body** :
```json
{
  "slug": "arctique-2026",
  "title": "Pourquoi l'Arctique...",
  "description": "...",
  "canonical_url": "https://youtube.com/...",
  "platform": "youtube"
}
```

**Réponse 201** : la fiche en brouillon, sans sources

**Validations** :
- `slug` matche la regex
- `slug` unique pour ce créateur
- `title` 1-200 chars
- `platform` IN (`youtube`, `podcast`, `blog`, `x`, `bluesky`, `other`)

---

### `PATCH /api/v1/cards/{id}` — modifier une fiche

Modifie les métadonnées d'une fiche (avant publication).

**Réponse 200** : la fiche mise à jour

**Restrictions** :
- Une fiche `published` ne peut plus être modifiée (sauf passage à `archived`)
- Seul le créateur peut modifier sa fiche

---

### `POST /api/v1/cards/{id}/sources` — ajouter une source

**Body** :
```json
{
  "url": "https://www.nature.com/articles/...",
  "title": "Quadrupled Arctic amplification...",
  "authors": "Rantanen et al.",
  "published_at": "2022-08-11",
  "source_type": "peer-reviewed",
  "annotation": "...",
  "is_pivot": true
}
```

**Réponse 201** : la source créée avec `id` et `archive_status: "pending"`

**Side-effect** : un job asynchrone est lancé pour archiver l'URL sur Wayback Machine.

---

### `PATCH /api/v1/sources/{id}` — modifier une source

**Restrictions** : seules les sources des fiches non publiées peuvent être modifiées par l'auteur.

---

### `DELETE /api/v1/sources/{id}` — supprimer une source

**Restrictions** : idem.

---

### `POST /api/v1/cards/{id}/publish` — publier une fiche

Calcule le hash, signe, et passe le status à `published`.

**Réponse 200** :
```json
{
  "id": "uuid",
  "status": "published",
  "content_hash": "hex64...",
  "signature": "base64...",
  "signed_at": "2026-03-14T18:42:00Z",
  "published_at": "2026-03-14T18:42:00Z",
  "public_url": "https://filum.app/@lea-c/arctique-2026"
}
```

**Validations** :
- Au moins 1 source dans la fiche
- Toutes les sources ont `archive_status` IN (`archived`, `failed`) — pas de `pending` (sinon attendre)

**Side-effects** :
- Génération de l'image OpenGraph
- Enregistrement d'un audit event

---

### `GET /api/v1/me/cards` — liste les fiches du créateur courant

**Réponse 200** : liste paginée des fiches.

**Query params** :
- `status` (optionnel) : filtre par statut
- `limit` : 1-100, défaut 20
- `cursor` : pour pagination cursor-based

---

### `GET /api/v1/cards/{id}/pdf` — export PDF de la fiche

Génère un PDF imprimable. Accessible publiquement (pas d'auth requise).

**Headers** : `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="filum-<slug>.pdf"`

---

## Endpoints d'analytics (admin / phase 2)

Réservés à l'admin Filum en phase 2 (à protéger par scope).

- `GET /api/v1/admin/stats` — statistiques globales (utilisateurs, fiches, sources)
- `GET /api/v1/admin/cards` — liste paginée de toutes les fiches publiées

---

## Format des erreurs

```json
{
  "error": {
    "code": "validation_error",
    "message": "Le slug doit contenir entre 3 et 80 caractères alphanumériques",
    "details": {
      "field": "slug",
      "value": "x"
    }
  }
}
```

**Codes d'erreur définis** :
- `validation_error` (400/422)
- `unauthorized` (401)
- `forbidden` (403)
- `not_found` (404)
- `conflict` (409, par ex. slug déjà pris)
- `rate_limited` (429)
- `internal_error` (500)
- `service_unavailable` (503, par ex. Wayback en panne)

---

## Validation stricte

Toutes les entrées sont validées par Pydantic v2 schemas avec :
- Length min/max sur les strings
- Regex sur les slugs
- Enum sur les types
- UUIDs valides
- URLs valides (avec scheme http/https uniquement)
- Pas de XSS dans les champs texte (échappement HTML côté frontend, mais validation backend aussi)

---

## Sécurité supplémentaire

- **CSRF** : token CSRF requis pour les routes mutables avec cookie session (sauf API avec Bearer token)
- **Same-Origin Policy** : appliquée par défaut
- **Audit logs** : toutes les actions mutables loguées dans `audit_events`

---

## Documentation API

FastAPI génère automatiquement une doc OpenAPI accessible à `/api/v1/docs` (Swagger UI) et `/api/v1/redoc` (ReDoc).

En production, ces routes peuvent être protégées ou désactivées (à arbitrer).

---

*Pour le design visuel des écrans qui consomment cette API, voir [`05-design-system.md`](./05-design-system.md).*
