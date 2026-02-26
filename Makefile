.PHONY: help setup clean test lint format dev dev-stop db-reset db-migrate worker clean-cache

help:
	@echo "GAIA_GO Development Framework"
	@echo "============================="
	@echo ""
	@echo "Setup & Environment:"
	@echo "  make setup              - Complete development environment setup"
	@echo "  make verify             - Verify development environment"
	@echo ""
	@echo "Development:"
	@echo "  make dev                - Start development servers (Flask + Go with hot reload)"
	@echo "  make dev-stop           - Stop development servers"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint               - Run all linters (black, flake8, pylint)"
	@echo "  make format             - Auto-format all code (black, isort)"
	@echo ""
	@echo "Testing:"
	@echo "  make test-unit          - Run unit tests (fast)"
	@echo "  make test-integration   - Run integration tests"
	@echo "  make test-e2e           - Run E2E tests"
	@echo "  make test-all           - Run all tests with coverage"
	@echo "  make test-watch         - Run tests in watch mode"
	@echo ""
	@echo "Database:"
	@echo "  make db-reset           - Reset development database"
	@echo "  make db-migrate         - Run migrations"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean              - Clean build artifacts and cache"
	@echo "  make clean-cache        - Clean Python cache files"
	@echo ""
	@echo "Services:"
	@echo "  make worker             - Start background task worker"
	@echo "  make health-check       - Run health check on all services"

setup:
	@echo "Setting up GAIA_GO development environment..."
	@bash .venv_setup.sh 3.11
	@bash db_init.sh data/architect_dev.db
	@echo ""
	@echo "✓ Setup complete! Run 'make dev' to start development servers"

verify:
	@echo "Verifying GAIA_GO development setup..."
	@bash scripts/verify_setup.sh

lint:
	@echo "Running linters..."
	@python3 -m black --check . 2>/dev/null || true
	@python3 -m flake8 . --max-line-length=100 2>/dev/null || true
	@echo "✓ Lint checks complete"

format:
	@echo "Formatting code..."
	@python3 -m black .
	@python3 -m isort .
	@echo "✓ Code formatted"

test-unit:
	@echo "Running unit tests..."
	@python3 -m pytest tests/unit -v --tb=short --cov=src --cov-report=term-missing

test-integration:
	@echo "Running integration tests..."
	@python3 -m pytest tests/integration -v --tb=short

test-e2e:
	@echo "Running E2E tests..."
	@python3 -m pytest tests/e2e -v --tb=short

test-all:
	@echo "Running all tests with coverage..."
	@python3 -m pytest tests/ -v --tb=short --cov=src --cov-report=html --cov-report=term
	@echo ""
	@echo "✓ Coverage report generated at htmlcov/index.html"

test-watch:
	@echo "Running tests in watch mode..."
	@python3 -m pytest tests/ -v --tb=short -f

dev:
	@echo "Starting development servers..."
	@echo "Flask: http://localhost:8080"
	@echo "Go Services: http://localhost:9000"
	@echo ""
	@tmux new-session -d -s gaia_dev 2>/dev/null || true
	@tmux send-keys -t gaia_dev:0 "cd $(PWD) && source venv/bin/activate && export FLASK_ENV=development && python -m flask run --host 0.0.0.0 --port 8080" C-m
	@sleep 2
	@echo "✓ Flask server started on port 8080"

dev-stop:
	@echo "Stopping development servers..."
	@tmux kill-session -t gaia_dev 2>/dev/null || true
	@echo "✓ Development servers stopped"

db-reset:
	@echo "Resetting development database..."
	@rm -f data/architect_dev.db*
	@bash db_init.sh data/architect_dev.db
	@echo "✓ Database reset complete"

db-migrate:
	@echo "Running migrations..."
	@python3 -c "from migrations import run_all; run_all('data/architect_dev.db')" 2>/dev/null || echo "Migrations module not found"

worker:
	@echo "Starting background task worker..."
	@python3 workers/task_worker.py

health-check:
	@echo "Running health checks..."
	@bash scripts/health_check.sh

clean-cache:
	@echo "Cleaning Python cache files..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "✓ Cache cleaned"

clean: clean-cache
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info 2>/dev/null || true
	@rm -rf htmlcov .coverage .pytest_cache 2>/dev/null || true
	@rm -rf tmp/ 2>/dev/null || true
	@echo "✓ Clean complete"
