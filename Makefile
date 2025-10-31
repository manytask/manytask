ROOT_DIR := manytask
DOCKER_COMPOSE_DEV := docker-compose.development.yml
TESTS_DIR := tests
ALEMBIC_CONFIG_PATH := manytask/alembic.ini

.PHONY: dev test reset-dev clean-db lint lint-fix setup install-deps check format install-hooks run-hooks makemigrations migrate downgrade history

check: format lint test

install-deps:
	curl -LsSf https://astral.sh/uv/install.sh | sh

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
	uv run pytest -n 4 --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

test-colima: install-deps
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" \
	python -m pytest --cov-report term-missing --cov=$(ROOT_DIR) $(TESTS_DIR)/

lint:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format --check $(ROOT_DIR) $(TESTS_DIR)
	uv run ruff check $(ROOT_DIR) $(TESTS_DIR)
	uv run mypy $(ROOT_DIR)

format:
	@command -v uv >/dev/null 2>&1 || { echo "\033[0;31mError: uv is not installed.\033[0m"; exit 1; }
	uv run ruff format $(ROOT_DIR) $(TESTS_DIR)
	uv run ruff check $(ROOT_DIR) $(TESTS_DIR) --fix

setup: install-deps install-hooks
	uv run mypy --install-types --non-interactive $(ROOT_DIR) $(TESTS_DIR)

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
