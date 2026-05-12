ROOT_DIR := manytask
TESTS_DIR := tests
# Recipes run with cwd = manytask/; checker lives at repo root.
CHECKER_DIR := ../checker/checker
CHECKER_TESTS_DIR := ../checker/tests
DOCKER_COMPOSE_DEV := docker-compose.development.yml
ALEMBIC_CONFIG_PATH := manytask/alembic.ini
DOCS_DIR := ../docs
DOCS_HTML_DIR := html

COMMON_YAML ?= ../common.example.yml
MANYTASK_CONFIG_OUT ?= ../.manytask.yml

# testcontainers may fail on some macOS Docker setups due to Ryuk connectivity issues.
# Allow overriding: `make test TESTCONTAINERS_RYUK_DISABLED=false`
TESTCONTAINERS_RYUK_DISABLED ?= true
export TESTCONTAINERS_RYUK_DISABLED

.PHONY: dev test reset-dev clean-db lint setup install-deps check format check-colima install-hooks run-hooks makemigrations migrate downgrade history docs test-colima copy-common-config

check: copy-common-config format lint test

check-colima: copy-common-config format lint test-colima

install-deps:
	curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync --active --all-extras
	cd ../checker && uv pip install -e .

install-hooks:
	uv run pre-commit install --install-hooks

run-hooks:
	uv run pre-commit run --all-files

dev:
	docker compose -f $(DOCKER_COMPOSE_DEV) down
	docker compose -f $(DOCKER_COMPOSE_DEV) up --build

clean-db:
	docker compose -f $(DOCKER_COMPOSE_DEV) down -v
	docker volume prune -f

reset-dev: clean-db
	docker compose -f $(DOCKER_COMPOSE_DEV) up --build

test: copy-common-config install-deps
	TESTCONTAINERS_RYUK_DISABLED=$(TESTCONTAINERS_RYUK_DISABLED) uv run pytest -n 4 --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

test-colima: copy-common-config install-deps
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" \
	uv run python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

lint:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format --check $(ROOT_DIR) $(CHECKER_DIR) $(TESTS_DIR) $(CHECKER_TESTS_DIR)
	uv run ruff check $(ROOT_DIR) $(CHECKER_DIR) $(TESTS_DIR) $(CHECKER_TESTS_DIR)/
	uv run mypy $(ROOT_DIR) $(CHECKER_DIR)

format:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format $(ROOT_DIR) $(CHECKER_DIR) $(TESTS_DIR) $(CHECKER_TESTS_DIR)
	uv run ruff check $(ROOT_DIR) $(CHECKER_DIR) $(TESTS_DIR) $(CHECKER_TESTS_DIR) --fix

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

docs:
	@command -v npm >/dev/null 2>&1 || { echo "\033[0;31mError: npm is not installed.\033[0m"; exit 1; }
	@command -v yfm >/dev/null 2>&1 || { echo "\033[0;31mError: yfm is not installed. Run: sudo npm i @diplodoc/cli -g\033[0m"; exit 1; }
	yfm -i $(DOCS_DIR) -o $(DOCS_HTML_DIR) --allow-custom-resources

copy-common-config:
	cp "$(COMMON_YAML)" "$(MANYTASK_CONFIG_OUT)"
