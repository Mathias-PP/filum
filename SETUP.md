# Setup Guide - Filum Project

Guide d'installation complet pour un data engineer rejoignant le projet Filum en 2026.

## Prérequis Système

### 1. Python 3.12+
```bash
# Vérifier la version
python3 --version  # Doit être >= 3.12

# Si nécessaire, installer via pyenv
pyenv install 3.12.13
pyenv global 3.12.13
```

### 2. uv - Gestionnaire Python ultra-rapide
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env  # ou source ~/.bashrc
uv --version  # Devrait afficher 0.11.x
```

### 3. Node.js 22 + pnpm
```bash
# Via nvm (recommandé)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 22
nvm use 22
node --version  # v22.x.x

# Installer pnpm
npm install -g pnpm
pnpm --version  # v11.x.x
```

### 4. Docker + Docker Compose
```bash
docker --version        # Docker 29.x
docker compose version  # Docker Compose v2.x
```

### 5. Git
```bash
git --version  # Git 2.43+
```

## Installation Rapide

```bash
# 1. Cloner le projet
git clone https://github.com/Mathias-PP/filum.git
cd filum

# 2. Configuration de l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (voir section Configuration)

# 3. Démarrer les services Docker (PostgreSQL)
make docker-up

# 4. Installer les dépendances backend
make backend-setup

# 5. Installer les dépendances frontend
make frontend-setup

# 6. Lancer les migrations
make migrate

# 7. (Optionnel) Peupler la DB avec des données de démo
make seed

# 8. Démarrer en mode développement
make dev
```

## Configuration Manuelle Detailed

### Backend Python

```bash
cd apps/backend

# Synchroniser les dépendances avec uv
uv sync

# Vérifier l'installation
uv run python -c "import fastapi; print(fastapi.__version__)"

# Linting
uv run ruff check .

# Type checking
uv run mypy app/

# Tests
uv run pytest tests/ -v
```

### Frontend SvelteKit

```bash
cd apps/frontend

# Installer les dépendances
pnpm install

# Lancer le dev server
pnpm dev

# Build production
pnpm build

# Tests
pnpm test

# Lint + Format
pnpm lint
pnpm format
```

### Analytics (dbt + DuckDB)

```bash
cd apps/analytics

# Installer les dépendances dbt
uv tool install dbt-duckdb

# Configurer dbt (première fois)
dbt init filum_analytics
dbt deps

# Runner les modèles
dbt run

# Générer la documentation
dbt docs generate
dbt docs serve
```

## Services Docker

### PostgreSQL 16
```bash
# Démarrer
docker compose up -d postgres

# Vérifier
docker exec -it filum-postgres pg_isready -U filum

# Logs
docker compose logs postgres

# Se connecter
psql -h localhost -p 5432 -U filum -d filum_dev
```

### DuckDB (optionnel - peut aussi utiliser Python direct)
```bash
# Via Docker
docker run -it --rm duckdb/duckdb

# Ou via Python
uv run python -c "import duckdb; print(duckdb.__version__)"
```

## Commandes Makefile

| Commande | Description |
|----------|-------------|
| `make setup` | Installation complète |
| `make dev` | Démarrer tous les services |
| `make backend` | Backend seul (port 8000) |
| `make frontend` | Frontend seul (port 5173) |
| `make test` | Tous les tests |
| `make lint` | Linting backend + frontend |
| `make migrate` | Exécuter les migrations Alembic |
| `make db-reset` | Reset complet de la DB |
| `make seed` | Données de démo |
| `make docker-up` | Démarrer PostgreSQL |
| `make docker-down` | Arrêter PostgreSQL |
| `make clean` | Nettoyer les build artifacts |

## Variables d'Environnement

```bash
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://filum:password@localhost:5432/filum_dev

# Session
SESSION_SECRET=$(openssl rand -hex 32)

# Crypto (pour les clés Ed25519)
MASTER_ENCRYPTION_KEY=$(openssl rand -hex 32)

# Google OAuth (créer sur Google Cloud Console)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

## Architecture des Dépendances

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                          │
│              SvelteKit + TypeScript                  │
│                    (pnpm)                            │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/REST
┌─────────────────────▼───────────────────────────────┐
│                    Backend                            │
│              FastAPI + SQLAlchemy 2                  │
│                  (uv sync)                           │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  OAuth   │  │  Crypto  │  │  Wayback API     │  │
│  │  (JWT)   │  │(Ed25519) │  │  (httpx async)   │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
    ┌────▼────┐              ┌─────▼─────┐
    │PostgreSQL│              │  DuckDB   │
    │(16)     │              │(dbt)     │
    │         │              │           │
    │users    │──────────▶  │analytics  │
    │biblio   │              │staging    │
    │sources  │              │marts      │
    └─────────┘              └───────────┘
```

## Outils par Composant

| Composant | Outil | Version |
|-----------|-------|---------|
| Python | uv | 0.11+ |
| Node.js | nvm | 0.40+ |
| Package Manager | pnpm | 11+ |
| Backend | FastAPI | 0.115+ |
| ORM | SQLAlchemy | 2.0.35+ |
| Validation | Pydantic | 2.10+ |
| Migrations | Alembic | 1.14+ |
| Database | PostgreSQL | 16+ |
| Analytics DB | DuckDB | 1.5+ |
| Data Transform | dbt-duckdb | 1.8+ |
| Crypto | cryptography | 44+ |
| Linter | ruff | 0.8+ |
| Tests | pytest | 8.3+ |
| Frontend | SvelteKit | 2+ |
| Styling | Tailwind | 3.4+ |

## Notes pour Data Engineers

1. **DuckDB ≠ PostgreSQL** : DuckDB est utilisé pour l'analytics (OLAP), PostgreSQL pour le transactionnel (OLTP).

2. **dbt sur DuckDB** : Le projet utilise `dbt-duckdb` pour transformer les données PostgreSQL → DuckDB pour l'analytique.

3. **Async everywhere** : Le backend est 100% async (FastAPI + SQLAlchemy async + asyncpg).

4. **Cryptographie** : Le projet implémente des signatures Ed25519 pour la traçabilité des sources. Familiarisez-vous avec:
   - RFC 8785 (JCS - JSON Canonicalization Scheme)
   - SHA-256
   - Ed25519 (EdDSA)

5. **Migrations** : Utiliser Alembic, jamais modifier manuellement le schéma PostgreSQL.

## Troubleshooting

### PostgreSQL ne démarre pas
```bash
docker compose down -v  # Supprimer les volumes
docker compose up -d postgres
```

### uv: command not found
```bash
export PATH="$HOME/.local/bin:$PATH"
# Ou ajouter dans ~/.bashrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Ports déjà utilisés
```bash
# Vérifier les ports
lsof -i :5432  # PostgreSQL
lsof -i :8000  # Backend
lsof -i :5173  # Frontend

# Arrêter les processus
kill <PID>
```

### Erreur de permissions Docker
```bash
sudo usermod -aG docker $USER
newgrp docker
```
