.PHONY: help install install-dev test lint format clean docker-build docker-run

help:
	@echo "VESPER Ingestion Service - Available Commands:"
	@echo ""
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make test          - Run unit tests"
	@echo "  make test-cov      - Run tests with coverage"
	@echo "  make lint          - Run linters (ruff)"
	@echo "  make format        - Format code (black + ruff)"
	@echo "  make typecheck     - Run type checking (mypy)"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo ""

install:
	pip install -e .

install-dev:
	pip install -e .
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=vesper_ingestion --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	mypy src/

format:
	black src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/

clean:
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t vesper-ingestion:latest .

docker-run:
	docker run --rm \
		--env-file .env \
		vesper-ingestion:latest validate

# Development commands
dev-fetch-apple:
	python -m vesper_ingestion.cli fetch -c 0000320193 -f 10-K -m 5

dev-list:
	python -m vesper_ingestion.cli list-filings

dev-validate:
	python -m vesper_ingestion.cli validate
