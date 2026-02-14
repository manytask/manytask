ROOT_DIR := manytask
DOCKER_COMPOSE_DEV := docker-compose.development.yml
TESTS_DIR := tests
ALEMBIC_CONFIG_PATH := manytask/alembic.ini

# testcontainers may fail on some macOS Docker setups due to Ryuk connectivity issues.
# Allow overriding: `make test TESTCONTAINERS_RYUK_DISABLED=false`
TESTCONTAINERS_RYUK_DISABLED ?= true
export TESTCONTAINERS_RYUK_DISABLED

.PHONY: dev test reset-dev clean-db lint lint-fix setup install-deps check format install-hooks run-hooks makemigrations migrate downgrade history

check: format lint test

check-colima: format lint test-colima

install-deps:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync --active --all-extras

install-hooks:
	uv install
	uv run pre-commit install --install-hooks

run-hooks:
	uv run pre-commit run --all-files

dev:
	docker-compose -f $(DOCKER_COMPOSE_DEV) down
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

clean-db:
	docker-compose -f $(DOCKER_COMPOSE_DEV) down -v
	docker volume prune -f

reset-dev: clean-db
	docker-compose -f $(DOCKER_COMPOSE_DEV) up --build

test: install-deps
	TESTCONTAINERS_RYUK_DISABLED=$(TESTCONTAINERS_RYUK_DISABLED) poetry run pytest -n 4 --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/
	# Run checker test suite from inside ./checker so `import checker.*` resolves correctly.
	# Use `-c /dev/null` to avoid inheriting repo-level pytest config, but force rootdir back to ./checker.
	cd checker && TESTCONTAINERS_RYUK_DISABLED=$(TESTCONTAINERS_RYUK_DISABLED) PYTHONPATH=. uv run pytest -c /dev/null --rootdir=. --import-mode=importlib -n 4 --skip-firejail tests

test-colima: install-deps
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" \
	python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

lint:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format --check $(ROOT_DIR) $(TESTS_DIR) checker/checker
	uv run ruff check $(ROOT_DIR) $(TESTS_DIR) checker/checker
	uv run mypy $(ROOT_DIR) checker/checker

format:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format $(ROOT_DIR) $(TESTS_DIR) checker/checker
	uv run ruff check $(ROOT_DIR) $(TESTS_DIR) checker/checker --fix

setup: install-deps install-hooks

makemigrations:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(msg)" ]; then \
		echo "\033[0;31mError: Environment variable msg not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make makemigrations msg=\"Add some value to some model\"'\033[0m"; \
		exit 1; \
	fi
	uv run alembic -c $(ALEMBIC_CONFIG_PATH) revision -m "$(msg)" --autogenerate || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

migrate:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(rev)" ]; then \
		echo "\033[0;31mError: Environment variable rev not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make migrate rev=head'\033[0m"; \
		exit 1; \
	fi
	uv run alembic -c $(ALEMBIC_CONFIG_PATH) upgrade "$(rev)" || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

downgrade:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	@ if [ -z "$(rev)" ]; then \
		echo "\033[0;31mError: Environment variable rev not set\033[0m"; \
		echo "\033[0;31mRun command like this 'make downgrade rev=-1'\033[0m"; \
		exit 1; \
	fi
	uv run alembic -c $(ALEMBIC_CONFIG_PATH) downgrade "$(rev)" || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }

history:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run alembic -c $(ALEMBIC_CONFIG_PATH) history
	@echo ""
	uv run alembic -c $(ALEMBIC_CONFIG_PATH) current || { echo "\033[33mWarning: Make sure that the database is running.\033[0m"; exit 1; }
