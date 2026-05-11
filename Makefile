# Makefile pour le projet Filum
# Commandes principales pour le développement local

.PHONY: help setup install-backend install-frontend install-analytics dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend format format-backend format-frontend migrate migrate-create seed analytics-refresh clean

help:
	@echo "Commandes Filum disponibles :"
	@echo ""
	@echo "  Setup et installation"
	@echo "    make setup             - installe toutes les dépendances (backend + frontend + analytics)"
	@echo "    make install-backend   - dépendances backend uniquement"
	@echo "    make install-frontend  - dépendances frontend uniquement"
	@echo "    make install-analytics - dépendances dbt uniquement"
	@echo ""
	@echo "  Développement"
	@echo "    make dev               - démarre backend + frontend en parallèle"
	@echo "    make dev-backend       - backend FastAPI sur :8000"
	@echo "    make dev-frontend      - frontend SvelteKit sur :5173"
	@echo ""
	@echo "  Base de données"
	@echo "    make migrate           - applique les migrations en attente"
	@echo "    make migrate-create    - crée une nouvelle migration (auto-générée)"
	@echo "    make seed              - peuple la BDD avec des données de démo"
	@echo ""
	@echo "  Analytics"
	@echo "    make analytics-refresh - recharge DuckDB depuis Postgres et exécute dbt run"
	@echo ""
	@echo "  Tests, lint, format"
	@echo "    make test              - tous les tests"
	@echo "    make test-backend      - tests backend uniquement"
	@echo "    make test-frontend     - tests frontend uniquement"
	@echo "    make lint              - linting backend + frontend"
	@echo "    make format            - formatage backend + frontend"
	@echo ""
	@echo "  Nettoyage"
	@echo "    make clean             - supprime les caches et builds"

setup: install-backend install-frontend install-analytics
	@echo "✓ Setup complet effectué"

install-backend:
	@echo "Installation des dépendances backend..."
	cd apps/backend && uv sync

install-frontend:
	@echo "Installation des dépendances frontend..."
	cd apps/frontend && pnpm install

install-analytics:
	@echo "Installation des dépendances analytics..."
	cd apps/analytics && uv pip install -r requirements.txt

dev:
	@echo "Démarrage backend + frontend..."
	@(make dev-backend &) && (make dev-frontend &) && wait

dev-backend:
	cd apps/backend && uv run uvicorn src.filum_api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd apps/frontend && pnpm dev

migrate:
	cd apps/backend && uv run alembic upgrade head

migrate-create:
	@read -p "Nom de la migration : " name; \
	cd apps/backend && uv run alembic revision --autogenerate -m "$$name"

seed:
	cd apps/backend && uv run python -m src.filum_api.scripts.seed

analytics-refresh:
	cd apps/backend && uv run python -m src.filum_api.scripts.load_to_duckdb
	cd apps/analytics && uv run dbt run

test: test-backend test-frontend

test-backend:
	cd apps/backend && uv run pytest -v

test-frontend:
	cd apps/frontend && pnpm test

lint: lint-backend lint-frontend

lint-backend:
	cd apps/backend && uv run ruff check src tests

lint-frontend:
	cd apps/frontend && pnpm lint

format: format-backend format-frontend

format-backend:
	cd apps/backend && uv run ruff format src tests
	cd apps/backend && uv run ruff check --fix src tests

format-frontend:
	cd apps/frontend && pnpm format

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".svelte-kit" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".duckdb" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Nettoyage terminé"
