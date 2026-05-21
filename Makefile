.PHONY: help install test test-cov format lint clean run-controller

help:  ## Show this help message
	@echo "LLMBench - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with Poetry
	@echo "📦 Installing dependencies..."
	poetry install --with dev
	@echo "✅ Done! Activate venv with: source .venv/bin/activate"

test:  ## Run tests
	poetry run pytest tests/ -v

test-cov:  ## Run tests with coverage report
	poetry run pytest tests/ --cov=src/llmbench --cov-report=term-missing --cov-report=html

test-fast:  ## Run tests without coverage
	poetry run pytest tests/ -v --tb=short -x

format:  ## Format code with Black
	poetry run black src/ tests/
	@echo "✅ Code formatted"

lint:  ## Run type checking with mypy
	poetry run mypy src/

check:  ## Run all checks (format, lint, test)
	@echo "🔍 Running all checks..."
	@make format
	@make lint
	@make test-cov
	@echo "✅ All checks passed!"

clean:  ## Clean up cache and temp files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage
	@echo "✅ Cleaned"

run-controller:  ## Start the controller server
	poetry run llmbench controller start --port 8000

setup:  ## Initial setup (Poetry + venv)
	./setup-venv.sh

# --- GCP Terraform commands ---
tf-init:  ## Initialize Terraform for GCP
	cd infrastructure/gcp && terraform init

tf-plan:  ## Preview GCP infrastructure changes (requires terraform.tfvars)
	cd infrastructure/gcp && terraform plan

tf-apply:  ## Provision GCP workers (requires terraform.tfvars)
	cd infrastructure/gcp && terraform apply

tf-destroy:  ## Destroy all GCP workers for a run
	cd infrastructure/gcp && terraform destroy

tf-output:  ## Show IPs and SSH commands for running workers
	cd infrastructure/gcp && terraform output

.DEFAULT_GOAL := help
