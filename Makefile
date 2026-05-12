.PHONY: help setup dev backend frontend test lint typecheck migrate seed clean docker-up docker-down

# Colors
GREEN  := \033[0;32m
YELLOW := \033[0;33m
NC     := \033[0m

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# === Python ===
PYTHON := python3
BACKEND := apps/backend
UV := ~/.local/bin/uv

# === Node ===
NODE_VERSION := 22
PNPM := pnpm

# === Docker ===
COMPOSE := docker compose

# === Setup ===
setup: docker-up backend-setup frontend-setup ## Full setup (requires sudo for Docker)

backend-setup: ## Install Python dependencies
	@echo "$(YELLOW)Installing Python dependencies...$(NC)"
	cd $(BACKEND) && $(UV) sync
	cd $(BACKEND) && $(UV) run ruff check .

frontend-setup: ## Install Node dependencies
	@echo "$(YELLOW)Installing Node dependencies...$(NC)"
	cd apps/frontend && $(PNPM) install
	cd apps/frontend && $(PNPM) run build

# === Development ===
dev: ## Start all services in dev mode
	@echo "$(YELLOW)Starting Filum development...$(NC)"
	cd $(BACKEND) && $(UV) run uvicorn app.main:app --reload --port 8000 &
	cd apps/frontend && $(PNPM) dev

backend: ## Start backend only
	@echo "$(YELLOW)Starting backend...$(NC)"
	cd $(BACKEND) && $(UV) run uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

frontend: ## Start frontend only
	@echo "$(YELLOW)Starting frontend...$(NC)"
	cd apps/frontend && $(PNPM) dev

# === Testing ===
test: ## Run all tests
	cd $(BACKEND) && $(UV) run pytest tests/ -v
	cd apps/frontend && $(PNPM) run test

test-backend: ## Run backend tests only
	cd $(BACKEND) && $(UV) run pytest tests/ -v

test-frontend: ## Run frontend tests only
	cd apps/frontend && $(PNPM) run test

# === Linting & Type Checking ===
lint: ## Run linters
	cd $(BACKEND) && $(UV) run ruff check .
	cd apps/frontend && $(PNPM) run lint

typecheck: ## Run type checkers
	cd $(BACKEND) && $(UV) run mypy app/
	cd apps/frontend && $(PNPM) run check

format: ## Format code
	cd $(BACKEND) && $(UV) run ruff format .
	cd apps/frontend && $(PNPM) run format

# === Database ===
migrate: ## Run Alembic migrations
	cd $(BACKEND) && $(UV) run alembic upgrade head

migrate-create: ## Create new migration (name required)
	cd $(BACKEND) && $(UV) run alembic revision --autogenerate -m "$(NAME)"

migrate-rollback: ## Rollback last migration
	cd $(BACKEND) && $(UV) run alembic downgrade -1

db-reset: ## Reset database (dangerous!)
	cd $(BACKEND) && $(UV) run alembic downgrade base
	cd $(BACKEND) && $(UV) run alembic upgrade head

seed: ## Seed database with demo data
	cd $(BACKEND) && $(UV) run python -m app.db.seed

# === Docker ===
docker-up: ## Start Docker services (PostgreSQL, DuckDB)
	@echo "$(YELLOW)Starting Docker services...$(NC)"
	$(COMPOSE) up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		nc -z localhost 5432 && break || sleep 1; \
	done

docker-down: ## Stop Docker services
	$(COMPOSE) down

docker-logs: ## Show Docker logs
	$(COMPOSE) logs -f

# === Analytics (dbt) ===
dbt-deps: ## Install dbt dependencies
	cd apps/analytics && $(UV) run dbt deps

dbt-run: ## Run dbt models
	cd apps/analytics && $(UV) run dbt run

dbt-test: ## Run dbt tests
	cd apps/analytics && $(UV) run dbt test

dbt-docs: ## Generate dbt documentation
	cd apps/analytics && $(UV) run dbt docs generate

# === Cleanup ===
clean: ## Clean build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	cd $(BACKEND) && $(UV) run pyclean . 2>/dev/null || true
	cd apps/frontend && $(PNPM) run clean || true
