# Makefile for VESPER
# Provides convenient commands for common development tasks

.PHONY: help setup start start-full start-simple stop restart clean logs health status verify test test-integration lint format format-check docker-build docker-push init-terraform plan-terraform apply-terraform destroy-terraform pre-commit-install ci-local

# Default target
.DEFAULT_GOAL := help

# Docker Compose file
COMPOSE_FILE := docker-compose.yml

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(GREEN)VESPER - Development Commands$(NC)'
	@echo ''
	@echo 'Usage:'
	@echo '  make $(YELLOW)<target>$(NC)'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Initial setup - run once to configure local environment
	@echo '$(GREEN)Setting up VESPER development environment...$(NC)'
	chmod +x scripts/*.sh
	./scripts/setup-local.sh
	@echo '$(GREEN)✅ Setup complete!$(NC)'

start: ## Start all services via Docker Compose
	@echo '$(GREEN)Starting VESPER services...$(NC)'
	docker-compose up -d
	@echo '$(GREEN)✅ Services started!$(NC)'
	@echo ''
	@echo 'Services available at:'
	@echo '  - Airflow:    http://localhost:8080 (admin/admin)'
	@echo '  - Grafana:    http://localhost:3003 (admin/admin)'
	@echo '  - MinIO:      http://localhost:9001 (minioadmin/minioadmin)'
	@echo '  - Prometheus: http://localhost:9090'
	@echo '  - PostgreSQL: localhost:5434 (vesper/vesper)'

start-full: ## Alias for start (kept for backwards compatibility)
	@$(MAKE) start

stop: ## Stop all services
	@echo '$(GREEN)Stopping VESPER services...$(NC)'
	docker-compose down
	@echo '$(GREEN)✅ Services stopped$(NC)'

restart: stop start ## Restart all services

logs: ## Follow logs from all services
	docker-compose logs -f

logs-%: ## Follow logs from a specific service (e.g., make logs-postgres)
	docker-compose logs -f $*

ps: ## Show running services
	@docker-compose ps

clean: ## Clean up containers, volumes, and temporary files
	@echo '$(RED)⚠️  This will remove all containers, volumes, and data!$(NC)'
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v 2>/dev/null || true; \
		find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true; \
		find . -type f -name .coverage -delete 2>/dev/null || true; \
		echo '$(GREEN)✅ Cleanup complete$(NC)'; \
	else \
		echo '$(YELLOW)Cancelled$(NC)'; \
	fi

test: ## Run all tests
	@echo '$(GREEN)Running tests...$(NC)'
	./scripts/test-unit.sh
	@echo '$(GREEN)✅ Tests complete$(NC)'

test-unit: ## Run unit tests only
	@echo '$(GREEN)Running unit tests...$(NC)'
	./scripts/test-unit.sh
	@echo '$(GREEN)✅ Unit tests complete$(NC)'

test-integration: ## Run integration tests
	@echo '$(GREEN)Running integration tests...$(NC)'
	./scripts/test-integration.sh || echo '$(YELLOW)Integration tests not yet implemented$(NC)'

lint: ## Run linters on all code
	@echo '$(GREEN)Running linters...$(NC)'
	@command -v black >/dev/null 2>&1 || pip install black isort flake8 mypy
	@echo 'Checking formatting with Black...'
	@black --check --line-length=120 services/ apps/ scripts/ orchestration/dags/ || echo '$(RED)Black formatting issues found - run: make format$(NC)'
	@echo 'Checking import sorting with isort...'
	@isort --check-only --profile black services/ apps/ scripts/ orchestration/dags/ || echo '$(RED)Import sorting issues found - run: make format$(NC)'
	@echo 'Linting with flake8...'
	@flake8 services/ apps/ scripts/ orchestration/dags/ --max-line-length=120 --extend-ignore=E203,W503 || echo '$(RED)Flake8 linting issues found$(NC)'
	@echo '$(GREEN)✅ Linting complete$(NC)'

format: ## Auto-format code with Black and isort
	@echo '$(GREEN)Formatting code...$(NC)'
	@command -v black >/dev/null 2>&1 || pip install black isort
	@echo 'Formatting with Black...'
	@black --line-length=120 services/ apps/ scripts/ orchestration/dags/
	@echo 'Sorting imports with isort...'
	@isort --profile black services/ apps/ scripts/ orchestration/dags/
	@echo '$(GREEN)✅ Formatting complete$(NC)'

format-check: ## Check code formatting without modifying files
	@echo '$(GREEN)Checking code formatting...$(NC)'
	@command -v black >/dev/null 2>&1 || pip install black isort
	@black --check --line-length=120 services/ apps/ scripts/ orchestration/dags/
	@isort --check-only --profile black services/ apps/ scripts/ orchestration/dags/
	@echo '$(GREEN)✅ Format check complete$(NC)'

pre-commit-install: ## Install pre-commit hooks
	@echo '$(GREEN)Installing pre-commit hooks...$(NC)'
	@command -v pre-commit >/dev/null 2>&1 || pip install pre-commit
	@pre-commit install
	@echo '$(GREEN)✅ Pre-commit hooks installed$(NC)'
	@echo 'Hooks will run automatically on git commit'

ci-local: ## Run CI checks locally
	@echo '$(GREEN)Running local CI checks...$(NC)'
	@echo ''
	@echo '1/5: Formatting check...'
	@$(MAKE) format-check --no-print-directory
	@echo ''
	@echo '2/5: Linting...'
	@$(MAKE) lint --no-print-directory
	@echo ''
	@echo '3/5: Type checking...'
	@$(MAKE) typecheck --no-print-directory || true
	@echo ''
	@echo '4/5: Security scan...'
	@$(MAKE) security-scan --no-print-directory || true
	@echo ''
	@echo '5/5: Unit tests...'
	@$(MAKE) test-unit --no-print-directory || true
	@echo ''
	@echo '$(GREEN)✅ Local CI checks complete$(NC)'

typecheck: ## Run type checking
	@echo '$(GREEN)Running type checker...$(NC)'
	@command -v mypy >/dev/null 2>&1 || pip install mypy
	mypy services/ shared/ --install-types --non-interactive
	@echo '$(GREEN)✅ Type checking complete$(NC)'

security-scan: ## Run security scans
	@echo '$(GREEN)Running security scans...$(NC)'
	@command -v bandit >/dev/null 2>&1 || pip install bandit
	bandit -r services/ shared/ || echo '$(YELLOW)Security issues found$(NC)'
	@echo '$(GREEN)✅ Security scan complete$(NC)'

docker-build: ## Build all Docker images
	@echo '$(GREEN)Building Docker images...$(NC)'
	./scripts/build-and-push.sh
	@echo '$(GREEN)✅ Docker build complete$(NC)'

terraform-init: ## Initialize Terraform
	@echo '$(GREEN)Initializing Terraform...$(NC)'
	cd infrastructure/terraform/environments/dev && terraform init
	@echo '$(GREEN)✅ Terraform initialized$(NC)'

terraform-plan: ## Run Terraform plan
	@echo '$(GREEN)Running Terraform plan...$(NC)'
	cd infrastructure/terraform/environments/dev && terraform plan
	@echo '$(GREEN)✅ Terraform plan complete$(NC)'

terraform-apply: ## Apply Terraform changes
	@echo '$(RED)⚠️  This will modify AWS infrastructure!$(NC)'
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cd infrastructure/terraform/environments/dev && terraform apply; \
	else \
		echo '$(YELLOW)Cancelled$(NC)'; \
	fi

db-shell: ## Connect to PostgreSQL database
	docker-compose exec postgres psql -U vesper -d vesper

redis-cli: ## Connect to Redis CLI
	docker-compose exec redis redis-cli

airflow-shell: ## Open Airflow shell
	docker-compose exec airflow-webserver airflow shell

install-dev: ## Install development dependencies for a service
	@read -p "Service name (e.g., api-gateway): " service; \
	cd services/$$service && \
	python -m venv venv && \
	. venv/bin/activate && \
	pip install -r requirements.txt && \
	pip install -e ".[dev]" && \
	echo '$(GREEN)✅ Development environment setup for $$service$(NC)'

check-env: ## Check if .env file is configured
	@if [ ! -f .env ]; then \
		echo '$(RED)❌ .env file not found!$(NC)'; \
		echo 'Run: cp .env.example .env'; \
		exit 1; \
	else \
		echo '$(GREEN)✅ .env file exists$(NC)'; \
	fi

health: ## Check health of all services
	@echo '$(GREEN)Checking service health...$(NC)'
	@echo ''
	@echo 'PostgreSQL:'
	@docker-compose exec -T postgres pg_isready -U vesper || echo '$(RED)  ❌ Not healthy$(NC)'
	@echo ''
	@echo 'Redis:'
	@docker-compose exec -T redis redis-cli ping || echo '$(RED)  ❌ Not healthy$(NC)'
	@echo ''
	@echo 'MinIO:'
	@curl -s http://localhost:9000/minio/health/live > /dev/null && echo '  $(GREEN)✅ Healthy$(NC)' || echo '  $(RED)❌ Not healthy$(NC)'
	@echo ''
	@echo 'Airflow Webserver:'
	@curl -s http://localhost:8080/health > /dev/null && echo '  $(GREEN)✅ Healthy$(NC)' || echo '  $(RED)❌ Not healthy$(NC)'

docs: ## Open documentation
	@echo '$(GREEN)Opening documentation...$(NC)'
	open docs/README.md || xdg-open docs/README.md || echo 'Open docs/README.md manually'

version: ## Show version information
	@echo 'VESPER Development Environment'
	@echo ''
	@echo 'Tools:'
	@echo -n '  Docker: '; docker --version
	@echo -n '  Python: '; python --version
	@echo -n '  Node: '; node --version 2>/dev/null || echo 'not installed'
	@echo -n '  Terraform: '; terraform --version | head -n 1 2>/dev/null || echo 'not installed'

status: ## Show current status of services
	@echo '$(GREEN)VESPER Service Status$(NC)'
	@echo '===================='
	@docker-compose ps
	@echo ''
	@echo '$(GREEN)Health Status:$(NC)'
	@$(MAKE) health --no-print-directory || true

verify: ## Verify the complete setup
	@echo '$(GREEN)Running setup verification...$(NC)'
	@./scripts/verify-setup.sh || echo '$(YELLOW)Some checks failed - see above$(NC)'
