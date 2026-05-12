# État du projet

> Ce fichier est un **document vivant**. Le mettre à jour à la fin de chaque session de travail significative.

---

## Date de la dernière mise à jour

**12 mai 2026**

---

## Phase courante

**Phase 1 - MVP Development** — Backend fonctionnel avec tests green

---

## Ce qui est fait

### Infrastructure & Setup
- [x] Configuration CI/CD GitHub Actions (ci.yml, cd.yml, analytics.yml, security.yml)
- [x] Pre-commit hooks (ruff, mypy, eslint, prettier, dbt-compile)
- [x] Docker Compose configs (dev, staging, production)
- [x] Alembic migrations setup + initial schema
- [x] dbt project configuration (DuckDB analytics)
- [x] EditorConfig + VSCode settings
- [x] Scripts utilitaires (deploy, backup, restore, health-check)

### Backend - Models & Schemas
- [x] SQLAlchemy models: User, BiblioCard, Source, AuditEvent
- [x] Pydantic v2 schemas: User, BiblioCard, Source, Auth
- [x] Database config avec async SQLAlchemy 2.0

### Backend - Services
- [x] Crypto: HashService (SHA-256), SigningService (Ed25519), KeyManager (AES-GCM)
- [x] WaybackService: archivage async des sources
- [x] AuthService: JWT sessions, OAuth Google helper
- [x] CardService: CRUD, publish, verify

### Backend - API Endpoints
- [x] Auth: /login, /callback, /logout, /me
- [x] Cards: CRUD, publish, public card endpoint
- [x] Sources: CRUD avec Wayback integration
- [x] Users: public profile endpoint

### Tests
- [x] 23 unit tests: crypto + schemas (100% pass)
- [x] FastAPI app load verified

---

## Ce qui est en cours

### Frontend
- Structure SvelteKit à implémenter
- Composants UI de base
- Intégration API client

---

## Ce qui est bloqué (et pourquoi)

Aucun blocage pour le MVP backend.

---

## Prochaines tâches (top 5)

1. **F01** - Finaliser OAuth Google callback (échange de token avec Google)
2. **F05** - Background worker pour Wayback Machine
3. **F07** - Page publique avec graphe D3.js (frontend)
4. **F09** - OpenGraph dynamique (génération image)
5. **F10** - Export PDF

---

## Decisions récentes notables

- **12/05/2026** : Adoption de Ruff comme linter/formatter Python
- **12/05/2026** : Architecture async complète pour le backend
- **12/05/2026** : CI/CD pipeline avec GitHub Actions
- **12/05/2026** : Utilisation AES-GCM au lieu de Fernet pour encryption
- **12/05/2026** : Renommage `metadata` → `event_metadata` dans AuditEvent

---

## Notes diverses

### Points d'attention
- Backend FastAPI fonctionnel avec 29 fichiers Python
- Tests unitaires passent (23/23)
- OAuth Google nécessite configuration credentials dans .env
- Wayback Machine API call en place mais pas encore en background worker

### TODO Backend
- [ ] Seed script pour données de démo
- [ ] Background worker (Celery/ARQ) pour Wayback
- [ ] Logging structuré (structlog)
- [ ] Metrics Prometheus
- [ ] Rate limiting plus fin

### TODO Frontend
- [ ] Setup SvelteKit complet
- [ ] Composants UI (design system)
- [ ] Graphe D3.js interactif
- [ ] SSR pour pages publiques

---

## Métriques

- Fichiers Python backend : 29
- Tests unitaires : 23 (100% pass)
- Endpoints API : ~15
- Modèles SQLAlchemy : 4
