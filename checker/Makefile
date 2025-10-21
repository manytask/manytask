#.RECIPEPREFIX = >>
# Default task to run when no task is specified
all: help

# Help task to display callable targets
help:
	@echo "Makefile commands:"
	@echo "test-unit        - Run unit tests with pytest"
	@echo "test-integration - Run integration tests with pytest"
	@echo "test-docstests   - Run doctests with pytest"
	@echo "test             - Run all tests with pytest"
	@echo "lint             - Lint and typecheck the code"
	@echo "format           - Format the code with black"
	@echo "docs-build       - Build the documentation"
	@echo "docs-deploy      - Deploy the documentation"
	@echo "docs-deploy-main - Deploy dev (main branch) version of the documentation"
	@echo "docs-serve       - Serve the documentation in development mode"
	@echo "help             - Display this help"

# Run unit tests only
.PHONY: test-unit
test-unit:
	@echo "[make] Running unit tests..."
	pytest --skip-integration --skip-doctest

# Run integration tests only
.PHONY: test-integration
test-integration:
	@echo "[make] Running integration tests..."
	pytest --skip-unit --skip-doctest

# Run doctests only
.PHONY: test-docstests
test-docstests:
	@echo "[make] Running doctests..."
	pytest --skip-unit --skip-integration

# Run all tests
.PHONY: test
test:
	@echo "[make] Running unit and integration tests..."
	pytest $(OPTIONS)

# Lint and typecheck the code
.PHONY: lint
lint:
	@echo "[make] Linting and typechecking the code..."
	ruff check -- checker tests
	mypy -- checker
	isort --check-only -- checker tests
	black --check -- checker tests

# Format the code with black and isort
.PHONY: format
format:
	@echo "[make] Formatting the code..."
	isort -- checker tests
	black -- checker tests

# Deploy the documentation
.PHONY: docs-deploy
docs-deploy:
	@echo "[make] Deploying the documentation..."
	mike deploy -b gh-pages `cat VERSION` --push --message "docs(auto): deploy docs for `cat VERSION`"
	mike set-default `cat VERSION`

# Deploy dev version of the documentation
.PHONY: docs-deploy-main
docs-deploy-main:
	@echo "[make] Deploying the documentation (main)..."
	mike deploy -b gh-pages main --push --message "docs(auto): deploy docs for main branch"

# Build the documentation
.PHONY: docs-build
docs-build:
	@echo "[make] Building the documentation..."
	python -m mkdocs build

# Serve the documentation in development mode
.PHONY: docs-serve
docs-serve:
	@echo "[make] Serve the documentation..."
	python -m mkdocs serve
