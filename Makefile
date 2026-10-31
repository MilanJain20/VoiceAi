.PHONY: help up down build logs backend frontend db-migrate db-upgrade db-downgrade test lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Docker ----
up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Build all containers
	docker compose build

logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail backend logs
	docker compose logs -f backend

logs-frontend: ## Tail frontend logs
	docker compose logs -f frontend

# ---- Backend ----
backend: ## Run backend locally (outside Docker)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test: ## Run backend tests
	cd backend && python -m pytest tests/ -v --tb=short

backend-lint: ## Lint backend
	cd backend && ruff check . && ruff format --check .

backend-format: ## Format backend code
	cd backend && ruff format .

# ---- Frontend ----
frontend: ## Run frontend locally (outside Docker)
	cd frontend && npm run dev

frontend-build: ## Build frontend
	cd frontend && npm run build

frontend-lint: ## Lint frontend
	cd frontend && npm run lint

# ---- Database ----
db-migrate: ## Create a new migration (usage: make db-migrate msg="description")
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending migrations
	cd backend && alembic upgrade head

db-downgrade: ## Rollback last migration
	cd backend && alembic downgrade -1

db-reset: ## Drop and recreate database
	docker compose exec postgres psql -U voiceai -d postgres -c "DROP DATABASE IF EXISTS voiceai;"
	docker compose exec postgres psql -U voiceai -d postgres -c "CREATE DATABASE voiceai;"
	cd backend && alembic upgrade head

# ---- Full Stack ----
dev: ## Start full dev environment
	@echo "Starting infrastructure..."
	docker compose up -d postgres redis
	@echo "Waiting for services..."
	@sleep 3
	@echo "Running migrations..."
	cd backend && alembic upgrade head
	@echo "Infrastructure ready. Start backend and frontend in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"
