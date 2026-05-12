# État du projet

> Ce fichier est un **document vivant**. Le mettre à jour à la fin de chaque session de travail significative.

---

## Date de la dernière mise à jour

**12 mai 2026**

---

## Phase courante

**Phase 1 - MVP Development** — Backend et Frontend fonctionnels

---

## Branches Git Commitées

| Branche | Status | Description |
|---------|--------|-------------|
| `feat/infrastructure-and-backend-mvp` | ✅ Pushé | 90 fichiers, CI/CD, backend FastAPI |
| `feat/frontend-sveltekit-mvp` | ✅ Pushé | 30 fichiers, SvelteKit + Tailwind |

---

## Ce qui est fait

### Infrastructure & Setup
- [x] Configuration CI/CD GitHub Actions
- [x] Pre-commit hooks
- [x] Docker Compose configs
- [x] Alembic migrations
- [x] dbt project (DuckDB analytics)
- [x] Scripts DevOps

### Backend - FastAPI
- [x] Models: User, BiblioCard, Source, AuditEvent
- [x] Schemas Pydantic v2
- [x] Crypto: SHA-256, Ed25519, AES-GCM
- [x] Services: Auth, Card, Wayback
- [x] API REST: auth, cards, sources, users
- [x] 23 unit tests (100% pass)

### Frontend - SvelteKit
- [x] Design system: Button, Input, Card, Avatar, Badge, Alert
- [x] API client typé
- [x] Stores: auth, cards
- [x] Routes: homepage, dashboard, public card, user profile
- [x] Tailwind CSS avec design tokens custom

---

## Prochaines étapes

1. **Merge des branches** via PR
2. **OAuth Google complet** (callback avec échange de token)
3. **Graphe D3.js** pour la visualisation interactive
4. **Page de création de fiche** (dashboard/new)
5. **Export PDF**

---

## Commandes pour continuer

```bash
# Merger les branches
git checkout main
git merge feat/infrastructure-and-backend-mvp
git merge feat/frontend-sveltekit-mvp
git push

# Démarrer le développement
make setup
make dev
```

---

## Secrets à configurer (.env)

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/filum_dev
SESSION_SECRET=$(openssl rand -hex 32)
MASTER_ENCRYPTION_KEY=$(openssl rand -hex 32)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```
