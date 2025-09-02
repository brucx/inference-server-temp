.PHONY: help install dev test lint format clean up down logs restart build

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	uv pip sync
	uv pip install -e ".[dev]"

dev: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker locally
	CUDA_VISIBLE_DEVICES=0 celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 -Q gpu-high,gpu-normal,gpu-low

flower: ## Run Flower for Celery monitoring
	celery -A app.tasks.celery_app flower --port=5555

test: ## Run tests
	pytest tests/ -v --tb=short

lint: ## Run linting
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

format: ## Format code
	black app/ tests/
	isort app/ tests/
	ruff check --fix app/ tests/

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf dist/
	rm -rf *.egg-info

up: ## Start all services with docker-compose
	docker-compose up -d --build

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart

build: ## Build Docker images
	docker build -f Dockerfile.api -t inference-api:latest .
	docker build -f Dockerfile.worker -t inference-worker:latest .

shell-api: ## Open shell in API container
	docker exec -it inference-api /bin/bash

shell-worker: ## Open shell in worker container
	docker exec -it inference-worker-0 /bin/bash

status: ## Show status of all services
	docker-compose ps

init-env: ## Initialize environment file
	cp .env.example .env
	@echo "Created .env file. Please update it with your configuration."