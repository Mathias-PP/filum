# Skill: Backend FastAPI

> Quand l'utiliser : nouvel endpoint, modification de service, schéma Pydantic, modèle SQLAlchemy.

## Contexte

Backend Python 3.12 + FastAPI **async** + SQLAlchemy 2.x async + Pydantic v2. Toutes les routes async, toutes les sessions DB async. Pas de blocking I/O dans une route async.

## Checklist d'exécution

### Pour un nouvel endpoint

1. **Décider l'emplacement** : `apps/backend/app/api/v1/endpoints/<resource>.py`. Suivre le pattern existant.
2. **Définir le schéma Pydantic** : `apps/backend/app/schemas/<resource>.py`. Pydantic v2. Préférer `from __future__ import annotations` + type hints.
3. **Définir le service** : la logique métier va dans `apps/backend/app/services/<domain>.py`, **pas** dans l'endpoint.
4. **L'endpoint** : signature async, `Depends(get_db)` pour la session, `Depends(get_current_user)` si auth requise.
5. **Selectinload anticipé** : si l'endpoint retourne un objet avec relations, faire le `selectinload` **avant** le `commit`. Sinon `MissingGreenlet` (cf. `PITFALLS.md` 1.4).
6. **Validation entrée** : Pydantic v2. Pour les URLs utilisateur : `HttpUrl` + guard SSRF (cf. `apps/backend/app/extractors/url_extractor.py`).
7. **Rate limiting** : sur les endpoints publics qui appellent des services externes ou coûteux, brancher `slowapi`. Cf. [`rate-limiting.md`](./rate-limiting.md).
8. **Tests** :
   - Unit dans `tests/unit/` (service isolé, mocks DB minimaux)
   - Integration dans `tests/integration/` (TestClient FastAPI + SQLite aiosqlite)
9. **Documentation** : docstring sur l'endpoint, Swagger générera le reste.

### Pour un nouveau modèle SQLAlchemy

1. Créer dans `apps/backend/app/models/<name>.py`, classe `PascalCase`.
2. Hériter de `Base` (`from app.db.database import Base`).
3. Importer le modèle dans `apps/backend/tests/conftest.py` **avant** `Base.metadata.create_all` (cf. ADR-012, sinon table pas créée en test).
4. Créer la migration Alembic — cf. [`alembic-migrations.md`](./alembic-migrations.md).
5. Définir relationships avec `back_populates` explicite des deux côtés.

### Pour une fonction qui touche au crypto

1. Utiliser `cryptography` (déjà dans le projet). Pas de `pycryptodome`.
2. Ed25519 pour les signatures, AES-GCM pour le chiffrement symétrique (ADR-009), HS256 (PyJWT) pour les JWT (ADR-014).
3. **Ne jamais** modifier le `canonical_hash` payload (cf. `apps/backend/app/services/card.py` 96-105 / 161-169). Cf. `PITFALLS.md` 1.3.
4. Tests obligatoires sur toute fonction crypto.

### Vérifications avant commit

```bash
cd apps/backend
uv run ruff format .              # AVANT chaque commit, pas juste --check
uv run ruff check .
uv run mypy app/ --ignore-missing-imports
uv run pytest tests/ -v           # ⚠️ ne tourne pas sur Windows, cf. PITFALLS 1.10
```

## Pièges spécifiques

- **`datetime.utcnow()`** déprécié Python 3.12. Cf. `PITFALLS.md` 1.5.
- **Variables d'env UPPERCASE** silencieusement ignorées. Lowercase obligatoire. Cf. `PITFALLS.md` 1.6.
- **`cors_origins` mal formaté** (JSON array). Cf. `PITFALLS.md` 1.7.
- **`samesite=lax` bloque cross-origin** — basculer en `samesite=none, secure=True` quand OAuth branché. Cf. `PITFALLS.md` 1.8 + skill OAuth.
- **`ruff format` oublié** avant commit. Cf. `PITFALLS.md` 1.9.
- **Tests qui ne tournent pas sur Windows** — faire confiance à la CI Linux. Cf. `PITFALLS.md` 1.10.
- **`MissingGreenlet`** après commit — anticiper le `selectinload`. Cf. `PITFALLS.md` 1.4.

## Fichiers à connaître

- `apps/backend/app/main.py` — entry point FastAPI
- `apps/backend/app/core/config.py` — settings via pydantic-settings (`case_sensitive=True`)
- `apps/backend/app/db/database.py` — engine + session async + `Base`
- `apps/backend/app/api/v1/endpoints/auth.py` — pattern auth complet (cookies, JWT)
- `apps/backend/app/services/card.py` — `canonical_hash` (INVARIANT, NE PAS MODIFIER)
- `apps/backend/app/services/auth.py` — JWT HS256, hash, etc.
- `apps/backend/app/crypto/` — Ed25519, AES-GCM
- `apps/backend/app/extractors/url_extractor.py` — pattern SSRF guard + Crossref/HTML
- `apps/backend/tests/conftest.py` — fixtures async + import explicite des modèles

## Pour aller plus loin

- ADR-009 (AES-GCM), ADR-010 (env vars lowercase), ADR-012 (tests aiosqlite),
- ADR-014 (PyJWT), ADR-015 (Railway deploy), ADR-016 (D3 + parent_source_id),
- ADR-017 (itération 2 — indicateurs, excerpts, JSON-LD, SSR)
- `.docs/02-tech-architecture.md`, `.docs/04-api-design.md`, `.docs/03-data-model.md`
